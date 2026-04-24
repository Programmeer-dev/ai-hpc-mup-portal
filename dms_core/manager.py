"""
Document Management System Manager
Upravljanje zahtjevima kroz kompletan workflow
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dms_core.models import (
    DmsRequest, RequestType, RequestStatus, RequestPriority,
    DocumentTemplate, RequestStatusHistory, RequestComment, TourismProperty
)
from municipality_utils import validate_municipality


class DmsManager:
    """Upravljanje Dokumentima i Zahtjevima"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.logger = logging.getLogger("dms_portal.dms_manager")

    def _get_request(self, request_id: int) -> Optional[DmsRequest]:
        return self.db.get(DmsRequest, request_id)
    
    # ============= KREIRANJE ZAHTJEVA =============
    
    def create_request(
        self,
        request_type: RequestType,
        user_id: str,
        user_email: str,
        user_city: str,
        details: Dict = None,
        description: str = None,
        reason: str = None
    ) -> DmsRequest:
        """Kreiraj novi zahtjev"""

        if user_city and not validate_municipality(user_city):
            raise ValueError("Nevalidna opština za korisnika.")
        
        # Učitaj template sa potrebnim dokumentima
        template = self.db.query(DocumentTemplate).filter(
            DocumentTemplate.request_type == request_type.value
        ).first()
        
        request = DmsRequest(
            request_type=request_type,
            user_id=user_id,
            user_email=user_email,
            user_city=user_city,
            details=details or {},
            description=description,
            reason=reason,
            status=RequestStatus.DRAFT,
            priority=RequestPriority.MEDIUM,
            required_documents=template.required_documents if template else [],
            estimated_completion=datetime.now() + timedelta(
                days=template.estimated_days if template else 15
            )
        )
        
        self.db.add(request)
        self.db.commit()
        
        return request
    
    # ============= WORKFLOW STATUS =============
    
    def submit_request(self, request_id: int, changed_by: str = None) -> bool:
        """Podnesi zahtjev (DRAFT → SUBMITTED)"""
        request = self._get_request(request_id)
        if not request:
            return False

        request.submitted_at = datetime.now()
        return self._change_status(
            request_id,
            RequestStatus.SUBMITTED,
            changed_by=changed_by,
            reason="Korisnik je podnio zahtjev"
        )
    
    def start_review(self, request_id: int, assigned_to: str) -> bool:
        """Počni pregled (SUBMITTED → UNDER_REVIEW)"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        request.assigned_to = assigned_to
        
        return self._change_status(
            request_id,
            RequestStatus.UNDER_REVIEW,
            changed_by=assigned_to,
            reason=f"Pregled započet od strane {assigned_to}"
        )
    
    def request_user_action(self, request_id: int, action_needed: str, changed_by: str) -> bool:
        """Zahtijevaj od korisnika akciju (→ PENDING_USER)"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        # Dodaj komentar koji vidi korisnik
        self.add_comment(
            request_id,
            author=changed_by,
            content=action_needed,
            author_type="admin",
            is_internal=False
        )
        
        return self._change_status(
            request_id,
            RequestStatus.PENDING_USER,
            changed_by=changed_by,
            reason=action_needed
        )
    
    def approve_request(self, request_id: int, approved_by: str, notes: str = None) -> bool:
        """Odobri zahtjev"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        request.completed_at = datetime.now()
        if notes:
            request.notes = notes
        
        return self._change_status(
            request_id,
            RequestStatus.APPROVED,
            changed_by=approved_by,
            reason=f"Zahtjev odobren. {notes or ''}"
        )
    
    def complete_request(self, request_id: int, completed_by: str) -> bool:
        """Označi zahtjev kao završen"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        request.completed_at = datetime.now()
        
        return self._change_status(
            request_id,
            RequestStatus.COMPLETED,
            changed_by=completed_by,
            reason="Zahtjev je završen i isporučen korisniku"
        )
    
    def reject_request(self, request_id: int, rejection_reason: str, rejected_by: str) -> bool:
        """Odbij zahtjev"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        request.rejection_reason = rejection_reason
        request.completed_at = datetime.now()
        
        # Dodaj javni komentar
        self.add_comment(
            request_id,
            author=rejected_by,
            content=f"Zahtjev odbijen. Razlog: {rejection_reason}",
            author_type="admin",
            is_internal=False
        )
        
        return self._change_status(
            request_id,
            RequestStatus.REJECTED,
            changed_by=rejected_by,
            reason=rejection_reason
        )
    
    def _change_status(
        self,
        request_id: int,
        new_status: RequestStatus,
        changed_by: str = None,
        reason: str = None
    ) -> bool:
        """Promijeni status i spremi u istoriju"""
        request = self._get_request(request_id)
        if not request:
            return False

        if not changed_by:
            raise ValueError("Promjena statusa zahtijeva korisnicki identitet.")
        
        old_status = request.status
        if old_status == new_status:
            return True

        if not self._is_transition_allowed(old_status, new_status):
            raise ValueError(f"Nedozvoljena tranzicija: {old_status.value} -> {new_status.value}")

        request.status = new_status
        request.updated_at = datetime.now()
        
        # Spremi u istoriju
        history = RequestStatusHistory(
            request_id=request_id,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            reason=reason
        )
        
        self.db.add(history)
        self.db.commit()
        self.logger.info(
            "Status change request_id=%s from=%s to=%s by=%s",
            request_id,
            old_status.value,
            new_status.value,
            changed_by,
        )
        
        return True

    def _is_transition_allowed(self, old_status: RequestStatus, new_status: RequestStatus) -> bool:
        allowed = {
            RequestStatus.DRAFT: {RequestStatus.SUBMITTED},
            RequestStatus.SUBMITTED: {RequestStatus.UNDER_REVIEW, RequestStatus.REJECTED},
            RequestStatus.UNDER_REVIEW: {
                RequestStatus.PENDING_USER,
                RequestStatus.APPROVED,
                RequestStatus.REJECTED,
            },
            RequestStatus.PENDING_USER: {RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW},
            RequestStatus.APPROVED: {RequestStatus.COMPLETED},
            RequestStatus.REJECTED: set(),
            RequestStatus.COMPLETED: set(),
        }
        return new_status in allowed.get(old_status, set())

    def get_available_transitions(self, request_id: int) -> List[RequestStatus]:
        request = self._get_request(request_id)
        if not request:
            return []
        candidates = [status for status in RequestStatus if status != request.status]
        return [status for status in candidates if self._is_transition_allowed(request.status, status)]

    def transition_request(
        self,
        request_id: int,
        new_status: RequestStatus,
        changed_by: str,
        actor_role: str = "admin",
        reason: str = None,
    ) -> bool:
        """Javni API za promjenu statusa kroz validirani workflow."""
        request = self._get_request(request_id)
        if not request:
            return False

        role = (actor_role or "").strip().lower()
        if role != "admin":
            # Korisniku je dozvoljen samo povratak iz PENDING_USER u SUBMITTED.
            allowed_user_transition = (
                request.user_id == changed_by
                and request.status == RequestStatus.PENDING_USER
                and new_status == RequestStatus.SUBMITTED
            )
            if not allowed_user_transition:
                raise PermissionError("Nemate dozvolu za ovu promjenu statusa.")

        return self._change_status(
            request_id=request_id,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )
    
    # ============= DOKUMENTA =============
    
    def upload_document(self, request_id: int, doc_name: str, file_path: str) -> bool:
        """Učitaj dokument na zahtjev"""
        request = self._get_request(request_id)
        if not request:
            return False
        
        current_docs = list(request.documents_metadata or [])
        current_docs.append({
            "name": doc_name,
            "file_path": file_path,
            "uploaded_at": datetime.now().isoformat(),
            "status": "pending_review"
        })
        request.documents_metadata = current_docs
        request.updated_at = datetime.now()
        
        self.db.commit()
        return True
    
    def get_required_documents(self, request_id: int) -> List[str]:
        """Vrni listu potrebnih dokumenata"""
        request = self._get_request(request_id)
        return request.required_documents if request else []
    
    # ============= KOMENTARI =============
    
    def add_comment(
        self,
        request_id: int,
        author: str,
        content: str,
        author_type: str = "user",
        is_internal: bool = False
    ) -> Optional[RequestComment]:
        """Dodaj komentar na zahtjev"""
        comment = RequestComment(
            request_id=request_id,
            author=author,
            content=content,
            author_type=author_type,
            is_internal=is_internal
        )
        
        self.db.add(comment)
        self.db.commit()
        
        return comment
    
    def get_visible_comments(self, request_id: int, for_user: bool = False) -> List[RequestComment]:
        """Vrni vidljive komentare"""
        query = self.db.query(RequestComment).filter(
            RequestComment.request_id == request_id
        )
        
        if for_user:
            query = query.filter(RequestComment.is_internal == False)
        
        return query.order_by(RequestComment.created_at).all()
    
    # ============= TURIZAM =============
    
    def register_tourism_property(
        self,
        request_id: int,
        owner_id: str,
        property_type: str,
        address: str,
        city: str,
        capacity: int,
        rooms: int,
        amenities: List[str] = None,
        coordinates: Dict = None
    ) -> Optional[TourismProperty]:
        """Registruj turističku nekretninu sa zahtjevom"""
        
        property = TourismProperty(
            property_type=property_type,
            owner_id=owner_id,
            address=address,
            city=city,
            capacity=capacity,
            rooms=rooms,
            amenities=amenities or [],
            coordinates=coordinates,
            registration_request_id=request_id
        )
        
        self.db.add(property)
        self.db.commit()
        
        return property
    
    # ============= PRETRAGA I FILTRIRANJE =============
    
    def get_user_requests(self, user_id: str) -> List[DmsRequest]:
        """Sve zahtjeve korisnika"""
        return self.db.query(DmsRequest).filter(
            DmsRequest.user_id == user_id
        ).order_by(DmsRequest.created_at.desc()).all()
    
    def get_active_requests(self) -> List[DmsRequest]:
        """Sve aktivne zahtjeve (nisu završeni)"""
        active_statuses = [
            RequestStatus.SUBMITTED,
            RequestStatus.UNDER_REVIEW,
            RequestStatus.PENDING_USER
        ]
        
        return self.db.query(DmsRequest).filter(
            DmsRequest.status.in_(active_statuses)
        ).order_by(DmsRequest.priority, DmsRequest.created_at).all()
    
    def get_overdue_requests(self) -> List[DmsRequest]:
        """Zahtjevi koji su prošli rok"""
        return self.db.query(DmsRequest).filter(
            DmsRequest.estimated_completion < datetime.now(),
            DmsRequest.status != RequestStatus.COMPLETED,
            DmsRequest.status != RequestStatus.REJECTED
        ).all()
    
    def get_requests_by_type(self, request_type: RequestType) -> List[DmsRequest]:
        """Zahtjevi određenog tipa"""
        return self.db.query(DmsRequest).filter(
            DmsRequest.request_type == request_type
        ).all()
    
    def get_assigned_requests(self, worker_id: str) -> List[DmsRequest]:
        """Zahtjevi dodijeljeni radniku"""
        return self.db.query(DmsRequest).filter(
            DmsRequest.assigned_to == worker_id
        ).order_by(
            DmsRequest.priority,
            DmsRequest.estimated_completion
        ).all()
    
    # ============= STATISTIKA =============
    
    def get_statistics(self) -> Dict:
        """Osnovne statistike DMS-a"""
        total = self.db.query(DmsRequest).count()
        
        statuses = {}
        for status in RequestStatus:
            count = self.db.query(DmsRequest).filter(
                DmsRequest.status == status
            ).count()
            statuses[status.value] = count
        
        avg_completion_time = self._calculate_avg_completion_time()
        
        return {
            "total_requests": total,
            "by_status": statuses,
            "avg_completion_days": avg_completion_time,
            "overdue_count": len(self.get_overdue_requests())
        }

    def get_kpi_metrics(self) -> Dict:
        """KPI metrike za dashboard i odbranu projekta."""
        total = self.db.query(DmsRequest).count()
        submitted = self.db.query(DmsRequest).filter(DmsRequest.submitted_at != None).count()
        completed = self.db.query(DmsRequest).filter(DmsRequest.status == RequestStatus.COMPLETED).count()

        pending_user_ids = {
            req_id
            for (req_id,) in self.db.query(RequestStatusHistory.request_id)
            .filter(RequestStatusHistory.to_status == RequestStatus.PENDING_USER)
            .distinct()
            .all()
        }

        first_review_hours = []
        submitted_requests = self.db.query(DmsRequest).filter(DmsRequest.submitted_at != None).all()
        for req in submitted_requests:
            first_review = (
                self.db.query(RequestStatusHistory)
                .filter(
                    RequestStatusHistory.request_id == req.id,
                    RequestStatusHistory.to_status == RequestStatus.UNDER_REVIEW,
                )
                .order_by(RequestStatusHistory.changed_at.asc())
                .first()
            )
            if first_review and req.submitted_at and first_review.changed_at:
                delta_hours = (first_review.changed_at - req.submitted_at).total_seconds() / 3600
                first_review_hours.append(max(delta_hours, 0))

        avg_first_review_hours = (
            round(sum(first_review_hours) / len(first_review_hours), 2) if first_review_hours else 0
        )

        completion_rate = round((completed / submitted) * 100, 2) if submitted else 0
        correction_rate = round((len(pending_user_ids) / submitted) * 100, 2) if submitted else 0

        return {
            "total_requests": total,
            "submitted_requests": submitted,
            "completed_requests": completed,
            "overdue_requests": len(self.get_overdue_requests()),
            "avg_first_review_hours": avg_first_review_hours,
            "completion_rate_percent": completion_rate,
            "correction_rate_percent": correction_rate,
        }

    def get_weekly_trends(self, weeks: int = 8) -> List[Dict]:
        """Vraća nedeljne KPI trendove za broj kreiranih, podnesenih i završenih zahtjeva."""
        weeks = max(2, min(weeks, 26))
        now = datetime.now()
        current_week_start = (now - timedelta(days=now.weekday())).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        first_week_start = current_week_start - timedelta(days=7 * (weeks - 1))

        buckets = {}
        for idx in range(weeks):
            week_start = first_week_start + timedelta(days=7 * idx)
            label = week_start.strftime("%Y-%m-%d")
            buckets[label] = {
                "week": label,
                "created": 0,
                "submitted": 0,
                "completed": 0,
            }

        requests = self.db.query(DmsRequest).filter(DmsRequest.created_at >= first_week_start).all()

        def add(metric_name: str, timestamp):
            if not timestamp or timestamp < first_week_start:
                return
            week_start = (timestamp - timedelta(days=timestamp.weekday())).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            label = week_start.strftime("%Y-%m-%d")
            if label in buckets:
                buckets[label][metric_name] += 1

        for req in requests:
            add("created", req.created_at)
            add("submitted", req.submitted_at)
            add("completed", req.completed_at)

        return [buckets[key] for key in sorted(buckets.keys())]

    def apply_sla_escalation(self) -> Dict:
        """Eskalira prioritet aktivnih predmeta koji kasne preko procijenjenog roka."""
        now = datetime.now()
        active_statuses = [
            RequestStatus.SUBMITTED,
            RequestStatus.UNDER_REVIEW,
            RequestStatus.PENDING_USER,
        ]
        active = self.db.query(DmsRequest).filter(DmsRequest.status.in_(active_statuses)).all()

        escalated = 0
        checked = 0
        for req in active:
            if not req.estimated_completion or req.estimated_completion >= now:
                continue

            checked += 1
            late_days = (now - req.estimated_completion).days
            target_priority = RequestPriority.URGENT if late_days >= 7 else RequestPriority.HIGH

            if req.priority != target_priority:
                req.priority = target_priority
                req.updated_at = now
                escalated += 1

        if escalated:
            self.db.commit()

        return {
            "checked_overdue": checked,
            "escalated": escalated,
        }

    def build_audit_pack(self, request_id: int) -> Dict:
        """Generiše audit izvještaj za pojedinačni predmet."""
        request = self._get_request(request_id)
        if not request:
            raise ValueError("Zahtjev nije pronađen.")

        history_rows = (
            self.db.query(RequestStatusHistory)
            .filter(RequestStatusHistory.request_id == request_id)
            .order_by(RequestStatusHistory.changed_at.asc())
            .all()
        )
        comment_rows = (
            self.db.query(RequestComment)
            .filter(RequestComment.request_id == request_id)
            .order_by(RequestComment.created_at.asc())
            .all()
        )

        return {
            "generated_at": datetime.now().isoformat(),
            "request": {
                "id": request.id,
                "request_type": request.request_type.value if request.request_type else None,
                "status": request.status.value if request.status else None,
                "priority": request.priority.value if request.priority else None,
                "user_id": request.user_id,
                "user_email": request.user_email,
                "user_city": request.user_city,
                "description": request.description,
                "reason": request.reason,
                "details": request.details or {},
                "documents_metadata": request.documents_metadata or [],
                "required_documents": request.required_documents or [],
                "created_at": request.created_at.isoformat() if request.created_at else None,
                "submitted_at": request.submitted_at.isoformat() if request.submitted_at else None,
                "updated_at": request.updated_at.isoformat() if request.updated_at else None,
                "completed_at": request.completed_at.isoformat() if request.completed_at else None,
                "assigned_to": request.assigned_to,
                "notes": request.notes,
                "rejection_reason": request.rejection_reason,
            },
            "status_history": [
                {
                    "from_status": row.from_status.value if row.from_status else None,
                    "to_status": row.to_status.value if row.to_status else None,
                    "changed_by": row.changed_by,
                    "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                    "reason": row.reason,
                }
                for row in history_rows
            ],
            "comments": [
                {
                    "author": row.author,
                    "author_type": row.author_type,
                    "is_internal": row.is_internal,
                    "content": row.content,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in comment_rows
            ],
        }
    
    def _calculate_avg_completion_time(self) -> float:
        """Prosječne dane za završetak zahtjeva"""
        completed = self.db.query(DmsRequest).filter(
            DmsRequest.status == RequestStatus.COMPLETED,
            DmsRequest.completed_at != None,
            DmsRequest.submitted_at != None
        ).all()
        
        if not completed:
            return 0
        
        total_days = 0
        for req in completed:
            delta = (req.completed_at - req.submitted_at).days
            total_days += delta
        
        return total_days / len(completed)
