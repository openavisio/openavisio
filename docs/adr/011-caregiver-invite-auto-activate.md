# Caregiver invites auto-activate on registration

When a Coordinator invites someone as a Caregiver for a Patient (or as a member of a Group), the access grant activates automatically when the invitee registers via the invite link — no second confirmation step from the Coordinator.

The Coordinator makes the trust decision when generating the invite. The invite token carries the Patient ID and access level, so registration is sufficient to complete the grant. A confirm-then-activate flow was considered but rejected: it adds friction without security gain, since the Coordinator already authorised the specific person at a specific access level when they sent the invite.

## Consequences

The invite token is the authorization. Tokens must have a short expiry (7 days, consistent with existing `UserInvitation` and `GroupInviteToken` models) and must be single-use. If the Coordinator sends an invite to the wrong person, they must revoke the grant after the fact — there is no interception point once the link is opened.
