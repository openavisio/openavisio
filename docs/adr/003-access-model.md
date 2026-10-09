# PatientAccess as the single access tier

The original code had three parallel access paths — Family membership, PatientRepresentation (legal), and PatientAccess (direct grant). After design review we collapsed these into one: PatientAccess is the sole access tier. Group (formerly Family) is a Coordinator convenience that bulk-creates PatientAccess grants but adds no separate tier. Legal representation (power of attorney, guardianship) is an attribute recorded on a PatientAccess grant for compliance purposes, not a separate path with different permissions.

The rejected alternative — keeping Family as a first-class access path — conflated a social relationship label with an access mechanism, forcing non-family caregivers (nurses, paid carers) through an ill-fitting "family" construct or through the legal-representation path, which implied formality they don't have.
