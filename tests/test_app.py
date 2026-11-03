import re

import pytest
from flask import template_rendered
from company_website import create_app
from company_website.config import Config
from company_website.db import get_db
from company_website.models import User
from company_website.routes import _contains_blocked_email_syntax, _render_email_preview


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SECRET_KEY', 'test-only-secret-key')
    monkeypatch.setattr(Config, 'DATABASE', str(tmp_path / 'database.db'))
    monkeypatch.setattr(Config, 'LEGACY_AUTH_DATABASE', str(tmp_path / 'legacy_auth.db'))
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_index(client):
    response = client.get('/')
    assert response.status_code == 200


def test_security_headers(client):
    response = client.get('/')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    assert response.headers['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()'


def test_login_page(client):
    response = client.get('/login')
    assert response.status_code == 200


def test_profile_redirects_when_not_logged_in(client):
    response = client.get('/profile', follow_redirects=False)
    assert response.status_code == 302


def test_disabled_user_existing_session_is_rejected(app, client):
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True

    with app.app_context():
        conn = get_db()
        conn.execute("UPDATE users SET enabled = 0 WHERE id = 1")
        conn.commit()
        conn.close()

    response = client.get('/profile', follow_redirects=False)

    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_employees_redirects_when_not_logged_in(client):
    response = client.get('/employees', follow_redirects=False)
    assert response.status_code == 302


def test_healthz_endpoint(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['db'] == 'connected'


def test_email_preview_supports_profile_variables(app):
    user = User(
        '1', 'sample', '', first_name='Ada', last_name='Lovelace',
        email='ada@example.com', role='Engineer'
    )

    with app.app_context():
        preview = _render_email_preview(
            'Hello {{ firstname }} {{ lastname }} ({{ email }}, {{ role }}) - {{ company }}',
            user,
        )

    assert preview == 'Hello Ada Lovelace (ada@example.com, Engineer) - Placeholder Industries'


@pytest.mark.parametrize('token', ['[]', "''", '()', 'dict', 'request'])
def test_email_preview_filter_blocks_listed_tokens(token):
    assert _contains_blocked_email_syntax(f'{{{{ value {token} }}}}')


@pytest.mark.parametrize('template', [
    '{{ config.SECRET_KEY }}',
    '{{ 7 * 7 }}',
    '{% for item in range(3) %}{{ item }}{% endfor %}',
    '{# hidden comment #}',
])
def test_email_preview_rejects_jinja_syntax(template):
    assert _contains_blocked_email_syntax(template)


def test_login_rejects_sql_injection(client):
    page = client.get('/login')
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = client.post('/login', data={
        'username': "' UNION SELECT 1,password_hash,'x',NULL,NULL,NULL,NULL,NULL,NULL FROM users WHERE username='flag' -- ",
        'password': 'x',
        'csrf_token': token,
    })

    assert response.status_code == 200
    assert b'Invalid username or password.' in response.data


@pytest.mark.parametrize('method', ['get', 'post'])
def test_profile_edit_forbids_other_users(client, method):
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True

    if method == 'post':
        page = client.get('/profiles/1/edit')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        response = client.post('/profiles/4/edit', data={'csrf_token': token})
    else:
        response = client.get('/profiles/4/edit')

    assert response.status_code == 403


def test_view_profile_hides_other_users_internal_notes(app, client):
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True

    rendered = []

    def record(sender, template, context, **extra):
        rendered.append(context['user'])

    with template_rendered.connected_to(record, app):
        other = client.get('/profiles/4')
        own = client.get('/profiles/1')

    assert other.status_code == 200
    assert own.status_code == 200
    assert rendered[0].internal_notes is None
    assert rendered[1].internal_notes


def test_profile_edit_rejects_missing_csrf_token(client):
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True

    response = client.post('/profiles/1/edit', data={'about': 'changed'})

    assert response.status_code == 400


def test_app_requires_configured_secret_key(monkeypatch):
    monkeypatch.setattr(Config, 'SECRET_KEY', None)

    with pytest.raises(RuntimeError, match='SECRET_KEY must be configured'):
        create_app()
