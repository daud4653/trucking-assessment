import uuid

from django.db import models
from django.db.models import Q


class RoutePlan(models.Model):
    """A computed route plan, kept for PLAN_RETENTION_HOURS.

    Plans are anonymous; the unguessable UUID is the only handle to one. The
    idempotency scope is a salted hash of the client address, never the
    address itself. Expired plans are removed by `purge_expired_plans`.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        COMPLETE = "complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    request_fingerprint = models.CharField(max_length=64)
    idempotency_scope = models.CharField(max_length=64, null=True, blank=True)  # noqa: DJ001
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)  # noqa: DJ001
    request = models.JSONField()
    result = models.JSONField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_scope", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="unique_idempotency_key_per_scope",
            )
        ]

    def __str__(self) -> str:
        return f"RoutePlan {self.id} ({self.status})"
