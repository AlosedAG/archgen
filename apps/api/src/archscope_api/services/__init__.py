"""Use cases. Each function takes and returns domain types (never HTTP
schemas) and is synchronous: they are CPU-bound or call the blocking
HubSpot SDK, so routers run them in the threadpool to keep the event loop
free. When persistence arrives (async SQLAlchemy), repository calls are
awaited in the routers/async services and the CPU work stays here."""
