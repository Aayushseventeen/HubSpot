import os
import httpx
from fastapi import Request, HTTPException, APIRouter
from dotenv import load_dotenv
from redis_client import add_key_value_redis, get_value_redis


load_dotenv()
router = APIRouter()

# HubSpot OAuth credentials
CLIENT_ID = os.getenv("HUBSPOT_CLIENT_ID")
CLIENT_SECRET = os.getenv("HUBSPOT_CLIENT_SECRET")
REDIRECT_URI = os.getenv("HUBSPOT_REDIRECT_URI")

# HubSpot API endpoints
TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts"

@router.get("/hubspot/authorize")
def authorize_hubspot(user_id: str, org_id: str):
    """Redirect user to HubSpot OAuth login"""
    auth_url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=crm.objects.contacts.read%20crm.objects.contacts.write%20crm.objects.companies.read%20crm.objects.deals.read%20oauth"    )
    return {"auth_url": auth_url}


@router.get("/hubspot/oauth2callback")
async def oauth2callback_hubspot(request: Request):
    """Handle OAuth callback and exchange code for access token."""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=payload)
            response.raise_for_status()
            token_data = response.json()

            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")

            # Store tokens in Redis
            await add_key_value_redis("hubspot_access_token", access_token, expire=expires_in)
            await add_key_value_redis("hubspot_refresh_token", refresh_token)

            return {"message": "Authorization successful! Tokens stored in Redis."}

        except httpx.HTTPStatusError as e:
            return {"error": "Failed to get access token", "details": str(e)}


async def refresh_access_token(refresh_token: str):
    """Refresh the HubSpot access token using the refresh token."""
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=payload)
            response.raise_for_status()
            token_data = response.json()

            # Store new tokens in Redis
            access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")

            await add_key_value_redis("hubspot_access_token", access_token, expire=expires_in)
            await add_key_value_redis("hubspot_refresh_token", new_refresh_token)

            return token_data

        except httpx.HTTPStatusError as e:
            return {"error": "Failed to refresh access token", "details": str(e)}


async def get_hubspot_credentials():
    """Retrieve stored HubSpot access token or refresh if expired."""
    access_token = await get_value_redis("hubspot_access_token")

    if access_token:
        return {"access_token": access_token.decode("utf-8")}

    # If access token is expired, try refreshing
    refresh_token = await get_value_redis("hubspot_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Access token expired, and no refresh token found. Please reauthorize.")

    # Refresh the access token
    new_token_data = await refresh_access_token(refresh_token.decode("utf-8"))
    if "access_token" not in new_token_data:
        raise HTTPException(status_code=401, detail="Failed to refresh access token. Please reauthorize.")

    return {"access_token": new_token_data["access_token"]}


async def create_integration_item_metadata_object(response_json):
    """Format HubSpot API response into a standardized format."""
    try:
        contacts = response_json.get("results", [])
        formatted_contacts = [
            {
                "id": contact.get("id"),
                "first_name": contact["properties"].get("firstname", ""),
                "last_name": contact["properties"].get("lastname", ""),
                "email": contact["properties"].get("email", ""),
            }
            for contact in contacts
        ]
        return {"contacts": formatted_contacts}

    except Exception as e:
        return {"error": f"Failed to process response: {str(e)}"}


@router.get("/hubspot/items")
async def get_items_hubspot():
    """Fetch contacts from HubSpot CRM using a valid access token."""
    credentials = await get_hubspot_credentials()
    access_token = credentials.get("access_token")

    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(CONTACTS_URL, headers=headers)
            response.raise_for_status()
            formatted_data = await create_integration_item_metadata_object(response.json())
            return formatted_data

        except httpx.HTTPStatusError as e:
            return {"error": "Failed to fetch contacts", "details": str(e)}
