t# OAuth Implementation

This folder contains the OAuth authentication implementation that was moved from the main app.py file. It provides Google and GitHub OAuth authentication capabilities.

## Files

- `oauth_config.py` - OAuth provider configuration and setup
- `oauth_routes.py` - OAuth routes and callback handlers
- `README.md` - This documentation file

## Usage

To integrate OAuth authentication back into the main application:

1. Install the required dependency:
   ```bash
   pip install authlib
   ```

2. Import and setup OAuth in your Flask app:
   ```python
   from oauth_implementation.oauth_config import setup_oauth
   from oauth_implementation.oauth_routes import register_oauth_routes
   
   # Setup OAuth
   oauth, google, github = setup_oauth(app)
   
   # Register OAuth routes
   register_oauth_routes(app, google, github)
   ```

3. Set environment variables for OAuth credentials:
   ```bash
   export GOOGLE_CLIENT_ID="your-google-client-id"
   export GOOGLE_CLIENT_SECRET="your-google-client-secret"
   export GITHUB_CLIENT_ID="your-github-client-id"
   export GITHUB_CLIENT_SECRET="your-github-client-secret"
   ```

## Features

- Google OAuth 2.0 authentication
- GitHub OAuth authentication
- Desktop app detection (falls back to basic auth)
- Session management with user info storage
- Error handling and fallback mechanisms

## Routes

- `/auth/<provider>` - Initiate OAuth login (google or github)
- `/callback/<provider>` - Handle OAuth callback from provider

## Session Data

When a user authenticates via OAuth, the following data is stored in the session:
- `user` - User identifier (email for Google, login for GitHub)
- `auth_method` - Authentication method used ('oauth_google' or 'oauth_github')
- `user_info` - Additional user information from the OAuth provider
