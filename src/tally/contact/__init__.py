"""
Tally Contact Engine: Interruption Budgets, Bundling, Value-First Composition, and Channels.
"""

from tally.contact.budget import ContactBudgetManager, MessageKind, SpendResult, SpendStatus
from tally.contact.bundler import BundledDispatch, CandidateMessage, MessageBundler
from tally.contact.channels import BaseChannel, ChannelDispatchError, MockChannel, SlackChannel
from tally.contact.composer import ComposedMessage, ComposerValidationResult, MessageComposer, SnoozeTracker

__all__ = [
    "ContactBudgetManager",
    "MessageKind",
    "SpendResult",
    "SpendStatus",
    "CandidateMessage",
    "BundledDispatch",
    "MessageBundler",
    "MessageComposer",
    "ComposedMessage",
    "ComposerValidationResult",
    "SnoozeTracker",
    "BaseChannel",
    "SlackChannel",
    "MockChannel",
    "ChannelDispatchError",
]
