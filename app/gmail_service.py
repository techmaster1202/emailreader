import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service(request):
    creds = None

    # Load credentials from session if available
    creds_dict = request.session.get('credentials')
    if creds_dict:
        creds = Credentials(**creds_dict)
    
    # Refresh credentials if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    # If no valid credentials, start OAuth2 flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri='http://127.0.0.1:8000/oauth2callback/'

        )
        authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
        request.session['oauth_state'] = state
        return authorization_url  # Return URL for user to authorize

    service = build('gmail', 'v1', credentials=creds)
    return service

def get_emails(request):
    service = get_gmail_service(request)
    if isinstance(service, str):
        # Redirect to OAuth2 authorization URL
        return service

    results = service.users().messages().list(userId='me').execute()
    messages = results.get('messages', [])

    emails = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        email_data = {
            'id': msg['id'],
            'snippet': msg['snippet'],
            'payload': msg['payload']
        }
        emails.append(email_data)

    return emails
