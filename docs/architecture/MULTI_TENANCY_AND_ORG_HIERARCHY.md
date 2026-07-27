# Multi-Tenancy and Configurable Organisational Hierarchy

Each HEI is an isolated tenant. Use generic `OrganizationalUnitType` and `OrganizationalUnit` entities so a tenant can define campus, college, faculty, school, department, centre, programme, qualification, discipline, course/module or other equivalents.

A role assignment records user, independent role, tenant, scope unit, descendant inheritance, valid-from/until, assignment reason, approver and status. Content may bind to multiple units and visibility groups. Enforcement occurs in backend repositories/services and is verified by tenant-isolation tests.
