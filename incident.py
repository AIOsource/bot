"""Incident clustering logic (v1.7.0)."""
from typing import Optional, List
from db_pkg import get_session, IncidentRepository, SignalRepository

class IncidentManager:
    """Manages incident lifecycle and clustering."""
    
    @staticmethod
    async def process_signal(
        signal_id: int,
        region: str,
        event_type: str,
        title: str
    ) -> int:
        """
        Process a new signal: attach to existing incident or create new.
        Returns incident_id.
        """
        async with get_session() as session:
            # 1. Try to find open similar incident
            # Simple clustering policy:
            # - Same Region
            # - Same Event Type
            # - Updated within last 24h
            # - Status is Open
            
            existing = await IncidentRepository.find_open_similar(
                session, 
                region=region,
                event_type=event_type,
                hours=24
            )
            
            if existing:
                # Attach to existing
                await IncidentRepository.increment_signal(session, existing.id)
                await session.commit()
                return existing.id
            
            # 2. Create new incident
            new_incident = await IncidentRepository.create(
                session,
                title=title,
                region=region,
                event_type=event_type
            )
            await session.commit()
            return new_incident.id
