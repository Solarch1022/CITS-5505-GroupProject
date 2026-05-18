import unittest

from src.app import create_app
from models import Item, User, Wallet, db


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def get_csrf_token(self):
        self.client.get('/')
        with self.client.session_transaction() as session:
            return session['csrf_token']

    def post_json(self, url, payload, csrf_token=None):
        headers = {}
        if csrf_token:
            headers['X-CSRF-Token'] = csrf_token
        return self.client.post(url, json=payload, headers=headers)

    def create_verified_user(self, username='seller', email='seller@student.uwa.edu.au', password='TestPass@123'):
        user = User(
            username=username,
            email=email,
            full_name='Test User',
            email_verified=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        db.session.add(Wallet(user_id=user.id, available_balance=100.0))
        db.session.commit()
        return user

    def login_user(self, username='seller', password='TestPass@123'):
        csrf_token = self.get_csrf_token()
        return self.post_json('/api/auth/login', {
            'username': username,
            'password': password,
        }, csrf_token=csrf_token)

    def valid_listing_payload(self):
        return {
            'title': 'Desk Lamp',
            'description': 'Bright LED lamp for study desks on campus.',
            'price': 15,
            'category': 'Electronics',
            'condition': 'Good',
            'quantity': 1,
        }

    def test_protected_api_requires_login(self):
        csrf_token = self.get_csrf_token()

        response = self.post_json('/api/items', self.valid_listing_payload(), csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 401)
        self.assertFalse(data['success'])
        self.assertIn('Unauthorized', data['error'])

    def test_csrf_blocks_unsafe_post_without_token(self):
        with self.app.app_context():
            self.create_verified_user()

        login_response = self.login_user()
        self.assertEqual(login_response.status_code, 200)

        response = self.client.post('/api/items', json=self.valid_listing_payload())
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])

    def test_unverified_user_cannot_login(self):
        with self.app.app_context():
            user = User(
                username='unverified',
                email='unverified@student.uwa.edu.au',
                full_name='Unverified User',
                email_verified=False,
            )
            user.set_password('TestPass@123')
            db.session.add(user)
            db.session.commit()

        csrf_token = self.get_csrf_token()
        response = self.post_json('/api/auth/login', {
            'username': 'unverified',
            'password': 'TestPass@123',
        }, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])
        self.assertIn('verify your email', data['error'])

    def test_verified_user_can_login_and_create_listing(self):
        with self.app.app_context():
            self.create_verified_user()

        login_response = self.login_user()
        self.assertEqual(login_response.status_code, 200)

        csrf_token = self.get_csrf_token()
        response = self.post_json('/api/items', self.valid_listing_payload(), csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['item']['title'], 'Desk Lamp')

        with self.app.app_context():
            item = Item.query.filter_by(title='Desk Lamp').first()
            self.assertIsNotNone(item)
            self.assertFalse(item.is_draft)
            self.assertEqual(item.category, 'Electronics')


if __name__ == '__main__':
    unittest.main()
