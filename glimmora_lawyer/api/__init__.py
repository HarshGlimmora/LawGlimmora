"""HTTP shim over the existing module services.

The frontend at ../frontend talks to this FastAPI app. Every router file
wraps existing services from `modules/**/services` without changing them.
"""
