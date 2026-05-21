import os
import requests
from typing import List
from dotenv import load_dotenv

# Import the strict schemas
# Using relative import since this is part of the core.communications package
try:
    from .schemas import ScheduleAPIResponse, ScheduleSchema, InstrumentMappingResponse
except ImportError:
    # Falling back to absolute import if running as a standalone script
    from schemas import ScheduleAPIResponse, ScheduleSchema, InstrumentMappingResponse

# Load environment variables
load_dotenv()

# Extract the configuration
PORTAL_API_URL = os.getenv("PORTAL_API_URL", "http://localhost:8000/")
# Ensure the URL ends with a slash for clean joining
if not PORTAL_API_URL.endswith('/'):
    PORTAL_API_URL += '/'

INSTRUMENT_API_URL = f"{PORTAL_API_URL}api/instruments/"
SCHEDULE_API_URL = f"{PORTAL_API_URL}api/schedule/"
API_TOKEN = os.getenv("PRAMANA_API_TOKEN")

def fetch_schedule() -> ScheduleAPIResponse:
    """
    Connects to the PRAMANA backend, authenticates, and returns 
    a strictly validated ScheduleAPIResponse object.
    """
    if not API_TOKEN:
        raise ValueError("CRITICAL: PRAMANA_API_TOKEN is missing from the .env file.")

    headers = {
        "Authorization": f"Token {API_TOKEN}", 
        "Content-Type": "application/json"
    }

    print(f"[SYSTEM] Connecting to PRAMANA at {SCHEDULE_API_URL}...")
    
    response = requests.get(SCHEDULE_API_URL, headers=headers)
    response.raise_for_status()

    print(f"[SYSTEM] Data received from {SCHEDULE_API_URL}. Validating...")
    validated_schedule = ScheduleAPIResponse.model_validate(response.json())
    print(f"[SYSTEM] Schedule validated successfully with {len(validated_schedule.results)} results.")
    return validated_schedule

def fetch_instruments() -> InstrumentMappingResponse:
    """
    Fetches the instrument-telescope mapping from PRAMANA.
    """
    if not API_TOKEN:
        raise ValueError("CRITICAL: PRAMANA_API_TOKEN is missing from the .env file.")

    headers = {
        "Authorization": f"Token {API_TOKEN}", 
        "Content-Type": "application/json"
    }

    print(f"[SYSTEM] Fetching hardware mapping from {INSTRUMENT_API_URL}...")
    
    response = requests.get(INSTRUMENT_API_URL, headers=headers)
    response.raise_for_status()

    print(f"[SYSTEM] Hardware mapping received. Validating structure...")
    validated_mapping = InstrumentMappingResponse.model_validate(response.json())
    print(f"[SYSTEM] Hardware mapping validated successfully.")
    return validated_mapping

def fetch_my_pending_tasks(my_telescope_id: str) -> List[ScheduleSchema]:
    """Dynamically fetches the schedule and filters for this specific LCU."""
    try:
        master_schedule = fetch_schedule()
        
        # FILTERING: Only grab tasks assigned to THIS telescope that are PENDING
        my_tasks = [
            obs for obs in master_schedule.results 
            if obs.telescope == my_telescope_id and obs.state == "PENDING"
        ]
        
        return my_tasks
        
    except requests.exceptions.HTTPError as http_err:
        print(f"[ERROR] API Authentication Failed. Details: {http_err}")
        return []
    except Exception as e:
        print(f"[ERROR] System failure: {e}")
        return []

if __name__ == "__main__":
    try:
        # Execute test fetch
        master_schedule = fetch_schedule()
        total_obs = len(master_schedule.results)
        print(f"[SYSTEM] Success! Downloaded {total_obs} observation tasks.")

        if total_obs > 0:
            first_obs = master_schedule.results[0]
            print("-" * 50)
            print("NEXT TARGET IN QUEUE:")
            print(f"Target:    {first_obs.request.configurations[0].target.name}")
            print(f"Telescope: {first_obs.telescope}")
            print("-" * 50)
            
    except Exception as e:
        print(f"[TEST ERROR] {e}")
