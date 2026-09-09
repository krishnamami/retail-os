"""Launch coordination agent for the Claris prototype.

Consumes governed readiness decisions. Produces explanations, a responsible
role, one recommended action and draft communications. Decides nothing.
"""

from .actions import ACTIONS, is_authorized  # noqa: F401
from .agent import LaunchCoordinationAgent  # noqa: F401
from .communication import (  # noqa: F401
    CHANNEL_EMAIL_DRAFT, CHANNEL_NOTE, CHANNELS, STATUS_DRAFT,
    STATUS_SUPERSEDED, Draft,
)
from .context import DEFAULT_HORIZON, LaunchContextLoader  # noqa: F401
from .models import (  # noqa: F401
    AgentResult, Blocker, LaunchCase, ReadinessView, Recommendation, WaitingOn,
)
from .reasoning import RESPONSIBLE_ROLE  # noqa: F401

__all__ = [
    "LaunchCoordinationAgent", "LaunchContextLoader", "DEFAULT_HORIZON",
    "AgentResult", "LaunchCase", "ReadinessView", "Blocker", "WaitingOn",
    "Recommendation", "Draft", "CHANNELS", "CHANNEL_NOTE",
    "CHANNEL_EMAIL_DRAFT", "STATUS_DRAFT", "STATUS_SUPERSEDED",
    "ACTIONS", "is_authorized", "RESPONSIBLE_ROLE",
]
