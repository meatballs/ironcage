from django.test import TestCase

from . import factories
from . import utils

from tickets import actions
from tickets.models import TicketInvitation


class NewOrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = factories.create_user()

    def test_get(self):
        self.client.force_login(self.alice)
        rsp = self.client.get('/tickets/orders/new/')
        self.assertInHTML('<tr><td>5 days</td><td>£138</td><td>£276</td></tr>', rsp.content.decode())
        self.assertContains(rsp, '<form method="post" id="order-form">')
        self.assertNotContains(rsp, 'Please create an account to buy a ticket.')

    def test_post_for_self(self):
        self.client.force_login(self.alice)
        form_data = {
            'who': 'self',
            'rate': 'individual',
            'days': ['thu', 'fri', 'sat'],
            # The formset gets POSTed even when order is only for self
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '1',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-email_addr': '',
            'form-1-email_addr': '',
        }
        rsp = self.client.post('/tickets/orders/new/', form_data, follow=True)
        self.assertContains(rsp, 'You have ordered 1 ticket(s)')

    def test_post_for_others(self):
        self.client.force_login(self.alice)
        form_data = {
            'who': 'others',
            'rate': 'individual',
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '1',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-email_addr': 'test1@example.com',
            'form-0-days': ['thu', 'fri'],
            'form-1-email_addr': 'test2@example.com',
            'form-1-days': ['sat', 'sun', 'mon'],
        }
        rsp = self.client.post('/tickets/orders/new/', form_data, follow=True)
        self.assertContains(rsp, 'You have ordered 2 ticket(s)')

    def test_post_for_self_and_others(self):
        self.client.force_login(self.alice)
        form_data = {
            'who': 'self and others',
            'rate': 'individual',
            'days': ['thu', 'fri', 'sat'],
            'form-TOTAL_FORMS': '2',
            'form-INITIAL_FORMS': '0',
            'form-MIN_NUM_FORMS': '1',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-email_addr': 'test1@example.com',
            'form-0-days': ['thu', 'fri'],
            'form-1-email_addr': 'test2@example.com',
            'form-1-days': ['sat', 'sun', 'mon'],
        }
        rsp = self.client.post('/tickets/orders/new/', form_data, follow=True)
        self.assertContains(rsp, 'You have ordered 3 ticket(s)')

    def test_get_when_not_authenticated(self):
        rsp = self.client.get('/tickets/orders/new/')
        self.assertInHTML('<tr><td>5 days</td><td>£138</td><td>£276</td></tr>', rsp.content.decode())
        self.assertNotContains(rsp, '<form method="post" id="order-form">')
        self.assertContains(rsp, 'Please create an account to buy a ticket.')

    def test_post_when_not_authenticated(self):
        rsp = self.client.post('/tickets/orders/new/', follow=True)
        self.assertRedirects(rsp, '/accounts/login/')


class OrderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = factories.create_confirmed_order_for_self()

    def test_order(self):
        self.client.force_login(self.order.purchaser)
        rsp = self.client.get(f'/tickets/orders/{self.order.order_id}/', follow=True)
        self.assertContains(rsp, f'Details of your order ({self.order.order_id})')

    def test_when_not_authenticated(self):
        rsp = self.client.get(f'/tickets/orders/{self.order.order_id}/', follow=True)
        self.assertRedirects(rsp, f'/accounts/login/?next=/tickets/orders/{self.order.order_id}/')
        self.assertContains(rsp, 'Please login to see this page.')

    def test_when_not_authorized(self):
        bob = factories.create_user(email_addr='bob@example.com')
        self.client.force_login(bob)
        rsp = self.client.get(f'/tickets/orders/{self.order.order_id}/', follow=True)
        self.assertRedirects(rsp, '/profile/')
        self.assertContains(rsp, 'Only the purchaser of an order can view the order')


class OrderPaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.order = factories.create_pending_order_for_self()

    def test_stripe_success(self):
        self.client.force_login(self.order.purchaser)
        with utils.patched_charge_creation_success():
            rsp = self.client.post(
                f'/tickets/orders/{self.order.order_id}/payment/',
                {'stripeToken': 'tok_abcdefghijklmnopqurstuvwx'},
                follow=True,
            )
        self.assertContains(rsp, 'Payment for this order has been received')
        self.assertNotContains(rsp, '<div id="stripe-form">')

    def test_stripe_failure(self):
        self.client.force_login(self.order.purchaser)
        with utils.patched_charge_creation_failure():
            rsp = self.client.post(
                f'/tickets/orders/{self.order.order_id}/payment/',
                {'stripeToken': 'tok_abcdefghijklmnopqurstuvwx'},
                follow=True,
            )
        self.assertContains(rsp, 'Payment for this order failed (Your card was declined.)')
        self.assertContains(rsp, '<div id="stripe-form">')

    def test_when_already_paid(self):
        factories.confirm_order(self.order)
        self.client.force_login(self.order.purchaser)
        rsp = self.client.post(
            f'/tickets/orders/{self.order.order_id}/payment/',
            {'stripeToken': 'tok_abcdefghijklmnopqurstuvwx'},
            follow=True,
        )
        self.assertRedirects(rsp, f'/tickets/orders/{self.order.order_id}/')
        self.assertContains(rsp, 'This order has already been paid')

    def test_when_not_authenticated(self):
        rsp = self.client.post(
            f'/tickets/orders/{self.order.order_id}/payment/',
            {'stripeToken': 'tok_abcdefghijklmnopqurstuvwx'},
            follow=True,
        )
        self.assertRedirects(rsp, f'/accounts/login/?next=/tickets/orders/{self.order.order_id}/payment/')
        self.assertContains(rsp, 'Please login to see this page.')

    def test_when_not_authorized(self):
        bob = factories.create_user(email_addr='bob@example.com')
        self.client.force_login(bob)
        rsp = self.client.post(
            f'/tickets/orders/{self.order.order_id}/payment/',
            {'stripeToken': 'tok_abcdefghijklmnopqurstuvwx'},
            follow=True,
        )
        self.assertRedirects(rsp, '/profile/')
        self.assertContains(rsp, 'Only the purchaser of an order can pay for the order')


class TicketTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ticket = factories.create_ticket()

    def test_ticket(self):
        self.client.force_login(self.ticket.owner)
        rsp = self.client.get(f'/tickets/tickets/{self.ticket.ticket_id}/', follow=True)
        self.assertContains(rsp, f'Details of your ticket ({self.ticket.ticket_id})')

    def test_when_not_authenticated(self):
        rsp = self.client.get(f'/tickets/tickets/{self.ticket.ticket_id}/', follow=True)
        self.assertRedirects(rsp, f'/accounts/login/?next=/tickets/tickets/{self.ticket.ticket_id}/')
        self.assertContains(rsp, 'Please login to see this page.')

    def test_when_not_authorized(self):
        bob = factories.create_user(email_addr='bob@example.com')
        self.client.force_login(bob)
        rsp = self.client.get(f'/tickets/tickets/{self.ticket.ticket_id}/', follow=True)
        self.assertRedirects(rsp, '/profile/')
        self.assertContains(rsp, 'Only the owner of a ticket can view the ticket')


class TicketInvitationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        factories.create_confirmed_order_for_others()
        cls.invitation = TicketInvitation.objects.get(email_addr='bob@example.com')
        cls.bob = factories.create_user(email_addr='bob@example.com', name='Bob')

    def test_for_unclaimed_invitation(self):
        self.client.force_login(self.bob)
        rsp = self.client.get(f'/tickets/invitations/{self.invitation.token}/', follow=True)
        self.assertContains(rsp, f'Details of your ticket ({self.invitation.ticket.ticket_id})')
        self.assertNotContains(rsp, 'This invitation has already been claimed', html=True)

    def test_for_claimed_invitation(self):
        self.client.force_login(self.bob)
        actions.claim_ticket_invitation(self.bob, self.invitation)
        rsp = self.client.get(f'/tickets/invitations/{self.invitation.token}/', follow=True)
        self.assertContains(rsp, f'Details of your ticket ({self.invitation.ticket.ticket_id})')
        self.assertContains(rsp, '<div class="alert alert-info" role="alert">This invitation has already been claimed</div>', html=True)

    def test_when_not_authenticated(self):
        rsp = self.client.get(f'/tickets/invitations/{self.invitation.token}/', follow=True)
        self.assertContains(rsp, '<div class="alert alert-info" role="alert">You need to create an account to claim your invitation</div>', html=True)
