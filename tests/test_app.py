import unittest

from src.app import create_app
from models import Conversation, Item, Message, PaymentMethod, Transaction, User, Wallet, WalletEntry, db


class MarketplaceAppTestCase(unittest.TestCase):
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

    def post_form(self, url, payload, csrf_token=None, follow_redirects=False):
        data = dict(payload)
        if csrf_token:
            data['csrf_token'] = csrf_token
        return self.client.post(url, data=data, follow_redirects=follow_redirects)

    def register_user(self, username, email, password='testpass123', full_name='Test User'):
        csrf_token = self.get_csrf_token()
        return self.post_json('/api/auth/register', {
            'username': username,
            'email': email,
            'password': password,
            'full_name': full_name,
        }, csrf_token=csrf_token)

    def login_user(self, username, password='testpass123'):
        csrf_token = self.get_csrf_token()
        return self.post_json('/api/auth/login', {
            'username': username,
            'password': password,
        }, csrf_token=csrf_token)

    def create_user(self, username, email, full_name='Test User'):
        user = User(username=username, email=email, full_name=full_name)
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()
        return user

    def link_payment_method(self, provider_name='CommBank', account_holder='Test User', account_number='4111111111111111'):
        csrf_token = self.get_csrf_token()
        return self.post_form('/wallet/payment-methods', {
            'provider_name': provider_name,
            'account_holder': account_holder,
            'account_number': account_number,
            'is_default': 'on',
        }, csrf_token=csrf_token)

    def top_up_wallet(self, amount, payment_method_id=None):
        csrf_token = self.get_csrf_token()
        payload = {'amount': amount}
        if payment_method_id:
            payload['payment_method_id'] = payment_method_id
        return self.post_form('/wallet/top-up', payload, csrf_token=csrf_token)

    def test_root_route_serves_home_page(self):
        response = self.client.get('/')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('UWA SecondHand', body)
        self.assertIn('Buy, sell, and message other UWA students in one place.', body)

    def test_browse_route_serves_template_page(self):
        response = self.client.get('/browse')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('Browse listings', body)
        self.assertIn('Campus filters', body)

    def test_register_rejects_non_uwa_email(self):
        response = self.register_user('outsider', 'outsider@gmail.com')
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('@student.uwa.edu.au', data['error'])

    def test_register_accepts_uwa_student_email(self):
        response = self.register_user('uwauser', 'uwauser@student.uwa.edu.au')
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertTrue(data['user']['is_uwa_verified'])

    def test_create_item_requires_csrf_token(self):
        self.register_user('seller', 'seller@student.uwa.edu.au')
        self.login_user('seller')

        response = self.client.post('/api/items', json={
            'title': 'Desk Lamp',
            'description': 'Bright LED lamp for study desks on campus.',
            'price': 15,
            'category': 'Electronics',
            'condition': 'Good',
        })
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])

    def test_authenticated_user_can_create_item(self):
        self.register_user('seller', 'seller@student.uwa.edu.au')
        self.login_user('seller')
        csrf_token = self.get_csrf_token()

        response = self.post_json('/api/items', {
            'title': 'Desk Lamp',
            'description': 'Bright LED lamp for study desks on campus.',
            'price': 15,
            'category': 'Electronics',
            'condition': 'Good',
        }, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['item']['title'], 'Desk Lamp')

    def test_wallet_payment_method_and_top_up_store_masked_details(self):
        self.register_user('walletuser', 'walletuser@student.uwa.edu.au')
        self.login_user('walletuser')

        link_response = self.link_payment_method()
        self.assertEqual(link_response.status_code, 302)

        with self.app.app_context():
            user = User.query.filter_by(username='walletuser').first()
            payment_method = PaymentMethod.query.filter_by(user_id=user.id).first()
            self.assertIsNotNone(payment_method)
            self.assertEqual(payment_method.last_four, '1111')
            self.assertIn('•••• 1111', payment_method.masked_details)
            self.assertNotIn('4111111111111111', payment_method.masked_details)

        top_up_response = self.top_up_wallet('75.00')
        self.assertEqual(top_up_response.status_code, 302)

        with self.app.app_context():
            user = User.query.filter_by(username='walletuser').first()
            wallet = Wallet.query.filter_by(user_id=user.id).first()
            top_up_entry = WalletEntry.query.filter_by(user_id=user.id, entry_type='top_up').first()
            self.assertIsNotNone(wallet)
            self.assertAlmostEqual(wallet.available_balance, 75.0)
            self.assertIsNotNone(top_up_entry)

    def test_save_draft_hides_listing_from_public_browse(self):
        self.register_user('seller', 'seller@student.uwa.edu.au')
        self.login_user('seller')
        csrf_token = self.get_csrf_token()

        response = self.post_form('/sell', {
            'title': 'Draft textbook bundle',
            'description': 'Need to check if all notes are still inside before publishing.',
            'price': '',
            'category': '',
            'condition': '',
            'intent': 'draft',
        }, csrf_token=csrf_token)

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            draft_item = Item.query.filter_by(title='Draft textbook bundle').first()
            self.assertIsNotNone(draft_item)
            self.assertTrue(draft_item.is_draft)

        browse = self.client.get('/browse')
        self.assertNotIn('Draft textbook bundle', browse.get_data(as_text=True))

    def test_unlist_moves_listing_into_draft_box(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au')
            item = Item(
                title='Lamp',
                description='Working desk lamp for sale.',
                price=18,
                category='Electronics',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('seller')
        csrf_token = self.get_csrf_token()
        response = self.post_form(f'/listings/{item_id}/unlist', {
            'decision': 'draft',
        }, csrf_token=csrf_token)

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            updated_item = db.session.get(Item, item_id)
            self.assertTrue(updated_item.is_draft)

    def test_delete_listing_removes_item_record(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au')
            item = Item(
                title='Mouse',
                description='Wireless mouse in good condition.',
                price=12,
                category='Electronics',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('seller')
        csrf_token = self.get_csrf_token()
        response = self.post_form(f'/listings/{item_id}/delete', {}, csrf_token=csrf_token)

        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            self.assertIsNone(db.session.get(Item, item_id))

    def test_purchase_uses_wallet_balance_and_credits_seller_wallet(self):
        with self.app.app_context():
            seller = self.create_user('sellerwallet', 'sellerwallet@student.uwa.edu.au', full_name='Seller Wallet')
            buyer = self.create_user('buyerwallet', 'buyerwallet@student.uwa.edu.au', full_name='Buyer Wallet')
            item = Item(
                title='Monitor',
                description='24-inch monitor suitable for campus study setups.',
                price=80,
                category='Electronics',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('buyerwallet')
        self.link_payment_method(provider_name='NAB', account_holder='Buyer Wallet', account_number='4000123412341234')
        self.top_up_wallet('100.00')
        csrf_token = self.get_csrf_token()
        purchase_response = self.post_form(f'/purchase/{item_id}', {}, csrf_token=csrf_token)
        self.assertEqual(purchase_response.status_code, 302)

        with self.app.app_context():
            transaction = Transaction.query.filter_by(item_id=item_id, status='completed').first()
            buyer = User.query.filter_by(username='buyerwallet').first()
            seller = User.query.filter_by(username='sellerwallet').first()
            buyer_wallet = Wallet.query.filter_by(user_id=buyer.id).first()
            seller_wallet = Wallet.query.filter_by(user_id=seller.id).first()
            purchase_entry = WalletEntry.query.filter_by(user_id=buyer.id, entry_type='purchase').first()
            sale_entry = WalletEntry.query.filter_by(user_id=seller.id, entry_type='sale_proceeds').first()
            item = db.session.get(Item, item_id)

            self.assertIsNotNone(transaction)
            self.assertTrue(item.is_sold)
            self.assertAlmostEqual(buyer_wallet.available_balance, 20.0)
            self.assertAlmostEqual(seller_wallet.available_balance, 80.0)
            self.assertIsNotNone(purchase_entry)
            self.assertIsNotNone(sale_entry)

    def test_purchase_fails_when_wallet_balance_is_insufficient(self):
        with self.app.app_context():
            seller = self.create_user('sellerlow', 'sellerlow@student.uwa.edu.au')
            buyer = self.create_user('buyerlow', 'buyerlow@student.uwa.edu.au')
            item = Item(
                title='Desk',
                description='Solid desk for a dorm room or study nook.',
                price=55,
                category='Furniture',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('buyerlow')
        csrf_token = self.get_csrf_token()
        response = self.post_json(f'/api/purchase/{item_id}', {}, csrf_token=csrf_token)
        data = response.get_json()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertIn('Insufficient wallet balance', data['error'])

    def test_withdrawal_applies_processing_fee(self):
        with self.app.app_context():
            user = self.create_user('withdrawuser', 'withdrawuser@student.uwa.edu.au', full_name='Withdraw User')
            wallet = Wallet(user_id=user.id, available_balance=120.0)
            method = PaymentMethod(
                user_id=user.id,
                provider_name='ANZ',
                account_holder='Withdraw User',
                masked_details='ANZ •••• 3456',
                last_four='3456',
                is_default=True,
            )
            db.session.add_all([wallet, method])
            db.session.commit()
            method_id = method.id

        self.login_user('withdrawuser')
        csrf_token = self.get_csrf_token()
        response = self.post_form('/wallet/withdraw', {
            'payment_method_id': method_id,
            'amount': '30.00',
        }, csrf_token=csrf_token)
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = User.query.filter_by(username='withdrawuser').first()
            wallet = Wallet.query.filter_by(user_id=user.id).first()
            withdrawal_entry = WalletEntry.query.filter_by(user_id=user.id, entry_type='withdrawal').first()
            fee_entry = WalletEntry.query.filter_by(user_id=user.id, entry_type='withdrawal_fee').first()

            self.assertAlmostEqual(wallet.available_balance, 89.4)
            self.assertIsNotNone(withdrawal_entry)
            self.assertIsNotNone(fee_entry)
            self.assertAlmostEqual(abs(fee_entry.amount), 0.6)

    def test_dashboard_masks_wallet_balances_by_default(self):
        with self.app.app_context():
            user = self.create_user('maskeduser', 'maskeduser@student.uwa.edu.au')
            wallet = Wallet(user_id=user.id, available_balance=88.75)
            db.session.add(wallet)
            db.session.commit()

        self.login_user('maskeduser')
        response = self.client.get('/dashboard')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-wallet-launch', body)
        self.assertIn('wallet-modal-backdrop hidden', body)
        self.assertIn('data-wallet-toggle', body)
        self.assertIn('data-wallet-sensitive', body)

    def test_dashboard_inbox_opens_conversation_only_after_selection(self):
        with self.app.app_context():
            seller = self.create_user('sellernews', 'sellernews@student.uwa.edu.au')
            buyer = self.create_user('buyernews', 'buyernews@student.uwa.edu.au')
            item = Item(
                title='Desk Organizer',
                description='Small organizer for campus stationery.',
                price=10,
                category='Other',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.flush()

            conversation = Conversation(item_id=item.id, seller_id=seller.id, buyer_id=buyer.id)
            db.session.add(conversation)
            db.session.flush()
            db.session.add(Message(conversation_id=conversation.id, sender_id=buyer.id, body='Is it still available?'))
            db.session.commit()
            conversation_id = conversation.id
            seller_username = seller.username

        self.login_user(seller_username)
        default_response = self.client.get('/dashboard')
        default_body = default_response.get_data(as_text=True)

        self.assertEqual(default_response.status_code, 200)
        self.assertIn('Latest news', default_body)
        self.assertIn('data-conversation-card', default_body)
        self.assertIn('data-latest-message-id', default_body)
        self.assertNotIn('Reply to this conversation...', default_body)
        self.assertNotIn('message-bubble', default_body)

        selected_response = self.client.get(f'/dashboard?conversation={conversation_id}')
        selected_body = selected_response.get_data(as_text=True)

        self.assertEqual(selected_response.status_code, 200)
        self.assertIn('Reply to this conversation...', selected_body)
        self.assertIn('Is it still available?', selected_body)

    def test_buyer_can_start_conversation_and_send_message(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au', full_name='Seller User')
            buyer = self.create_user('buyer', 'buyer@student.uwa.edu.au', full_name='Buyer User')
            item = Item(
                title='Mini Fridge',
                description='Working mini fridge suitable for dorm rooms.',
                price=120,
                category='Electronics',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        self.login_user('buyer')
        csrf_token = self.get_csrf_token()

        start_response = self.post_json(f'/api/items/{item_id}/conversations', {
            'message': 'Hi, can I inspect this on campus tomorrow?',
        }, csrf_token=csrf_token)
        start_data = start_response.get_json()

        self.assertEqual(start_response.status_code, 200)
        self.assertTrue(start_data['success'])
        self.assertEqual(start_data['conversation']['message_count'], 1)

        conversation_id = start_data['conversation']['id']
        send_response = self.post_json(f'/api/conversations/{conversation_id}/messages', {
            'message': 'I am free after 3pm.',
        }, csrf_token=csrf_token)
        send_data = send_response.get_json()

        self.assertEqual(send_response.status_code, 201)
        self.assertTrue(send_data['success'])
        self.assertEqual(len(send_data['conversation']['messages']), 2)

    def test_item_page_uses_compact_contact_entry_for_buyers_only(self):
        with self.app.app_context():
            seller = self.create_user('sellercontact', 'sellercontact@student.uwa.edu.au')
            buyer = self.create_user('buyercontact', 'buyercontact@student.uwa.edu.au')
            item = Item(
                title='Textbook Set',
                description='Useful textbooks for first-year campus units.',
                price=45,
                category='Books',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id
            buyer_username = buyer.username
            seller_username = seller.username

        self.login_user(buyer_username)
        buyer_response = self.client.get(f'/item/{item_id}')
        buyer_body = buyer_response.get_data(as_text=True)

        self.assertEqual(buyer_response.status_code, 200)
        self.assertIn('id="contact-seller"', buyer_body)
        self.assertIn('Icebreaker message', buyer_body)
        self.assertIn('Is it still available?', buyer_body)
        self.assertNotIn('data-chat-root', buyer_body)

        self.login_user(seller_username)
        seller_response = self.client.get(f'/item/{item_id}')
        seller_body = seller_response.get_data(as_text=True)

        self.assertEqual(seller_response.status_code, 200)
        self.assertNotIn('id="contact-seller"', seller_body)
        self.assertNotIn('Icebreaker message', seller_body)

    def test_item_contact_form_redirects_to_inbox_conversation(self):
        with self.app.app_context():
            seller = self.create_user('sellerinbox', 'sellerinbox@student.uwa.edu.au')
            buyer = self.create_user('buyerinbox', 'buyerinbox@student.uwa.edu.au')
            item = Item(
                title='Campus Chair',
                description='Comfortable chair for a study desk.',
                price=30,
                category='Furniture',
                condition='Good',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id
            buyer_id = buyer.id
            buyer_username = buyer.username
            seller_username = seller.username

        self.login_user(buyer_username)
        csrf_token = self.get_csrf_token()
        response = self.post_form(f'/item/{item_id}/conversation', {
            'message': 'Is it still available?',
        }, csrf_token=csrf_token)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard?conversation=', response.headers['Location'])
        self.assertIn('#inbox', response.headers['Location'])

        with self.app.app_context():
            conversation = Conversation.query.filter_by(item_id=item_id, buyer_id=buyer_id).first()
            self.assertIsNotNone(conversation)
            self.assertEqual(conversation.messages[0].body, 'Is it still available?')
            conversation_id = conversation.id

        self.login_user(seller_username)
        seller_dashboard = self.client.get(f'/dashboard?conversation={conversation_id}')
        seller_body = seller_dashboard.get_data(as_text=True)

        self.assertEqual(seller_dashboard.status_code, 200)
        self.assertIn('Campus Chair', seller_body)
        self.assertIn('Is it still available?', seller_body)

    def test_conversation_access_is_restricted_to_participants(self):
        with self.app.app_context():
            seller = self.create_user('seller', 'seller@student.uwa.edu.au')
            buyer = self.create_user('buyer', 'buyer@student.uwa.edu.au')
            outsider = self.create_user('outsider', 'outsider@student.uwa.edu.au')
            item = Item(
                title='Bike',
                description='Second-hand bike in rideable condition.',
                price=90,
                category='Sports',
                condition='Fair',
                seller_id=seller.id,
            )
            db.session.add(item)
            db.session.flush()

            conversation = Conversation(item_id=item.id, seller_id=seller.id, buyer_id=buyer.id)
            db.session.add(conversation)
            db.session.flush()
            db.session.add(Message(conversation_id=conversation.id, sender_id=buyer.id, body='Is this still available?'))
            db.session.commit()

            conversation_id = conversation.id
            outsider_username = outsider.username

        self.login_user(outsider_username)
        response = self.client.get(f'/api/conversations/{conversation_id}')
        data = response.get_json()

        self.assertEqual(response.status_code, 403)
        self.assertFalse(data['success'])


if __name__ == '__main__':
    unittest.main()
