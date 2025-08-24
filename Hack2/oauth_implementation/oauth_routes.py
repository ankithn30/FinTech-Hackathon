"""
OAuth Routes and Handlers
This module contains OAuth-related routes for Google and GitHub authentication.
"""

from flask import request, jsonify, redirect, url_for, session
from urllib.parse import quote_plus, urlencode

def register_oauth_routes(app, google, github):
    """Register OAuth routes with the Flask app"""
    
    def is_desktop_request():
        """Check if request is from desktop application"""
        user_agent = request.headers.get('User-Agent', '').lower()
        return 'desktop' in user_agent or 'electron' in user_agent or request.headers.get('X-Desktop-App') == 'true'

    @app.route('/auth/<provider>')
    def oauth_login(provider):
        """Initiate OAuth login with specified provider"""
        if is_desktop_request():
            # Desktop requests should use basic auth
            return redirect('/login')
        
        if provider == 'google':
            redirect_uri = url_for('oauth_callback', provider='google', _external=True)
            return google.authorize_redirect(redirect_uri)
        elif provider == 'github':
            redirect_uri = url_for('oauth_callback', provider='github', _external=True)
            return github.authorize_redirect(redirect_uri)
        else:
            return jsonify({'error': 'Unsupported OAuth provider'}), 400

    @app.route('/callback/<provider>')
    def oauth_callback(provider):
        """Handle OAuth callback from provider"""
        try:
            if provider == 'google':
                token = google.authorize_access_token()
                user_info = token.get('userinfo')
                if user_info:
                    session['user'] = user_info.get('email', user_info.get('name', 'Unknown'))
                    session['auth_method'] = 'oauth_google'
                    session['user_info'] = {
                        'name': user_info.get('name'),
                        'email': user_info.get('email'),
                        'picture': user_info.get('picture')
                    }
                    return redirect('/')
            elif provider == 'github':
                token = github.authorize_access_token()
                resp = github.get('user', token=token)
                user_info = resp.json()
                if user_info:
                    session['user'] = user_info.get('login', user_info.get('name', 'Unknown'))
                    session['auth_method'] = 'oauth_github'
                    session['user_info'] = {
                        'name': user_info.get('name'),
                        'login': user_info.get('login'),
                        'email': user_info.get('email'),
                        'avatar_url': user_info.get('avatar_url')
                    }
                    return redirect('/')
            
            return jsonify({'error': 'OAuth authentication failed'}), 400
            
        except Exception as e:
            print(f"OAuth callback error: {e}")
            return redirect('/login?error=oauth_failed')

    return app
