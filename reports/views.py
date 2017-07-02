from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views.generic import TemplateView

from cfp.models import Proposal
from tickets.constants import DAYS
from tickets.models import Order, Ticket
from tickets.prices import cost_incl_vat


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ReportView(TemplateView):
    template_name = 'reports/report.html'

    def get_context_data(self):
        return {
            'title': self.title,
            'headings': self.headings,
            'rows': [self.presenter(item) for item in self.get_queryset()],
        }

    @classmethod
    def path(cls):
        return f'^{slugify(cls.title)}/$'

    @classmethod
    def url_name(cls):
        return slugify(cls.title)

    @classmethod
    def namespaced_url_name(cls):
        return f'reports:{cls.url_name()}'


class AttendanceByDayReport(ReportView):
    title = 'Attendance by day'

    def get_context_data(self):
        tickets = Ticket.objects.all()

        rows = []

        for day in DAYS:
            num_tickets = {
                'individual': 0,
                'corporate': 0,
            }

            for ticket in tickets:
                if getattr(ticket, day):
                    num_tickets[ticket.order.rate] += 1

            rows.append([
                DAYS[day],
                num_tickets['individual'],
                num_tickets['corporate'],
                num_tickets['individual'] + num_tickets['corporate'],
            ])

        return {
            'title': self.title,
            'headings': ['Day', 'Individual rate', 'Corporate rate', 'Total'],
            'rows': rows,
        }


class TicketSalesReport(ReportView):
    title = 'Ticket sales'
    template_name = 'reports/ticket_sales_report.html'

    def get_context_data(self):
        tickets = Ticket.objects.all()

        num_tickets_rows = []
        ticket_cost_rows = []

        for ix in range(5):
            num_days = ix + 1
            individual_rate = cost_incl_vat('individual', num_days)
            corporate_rate = cost_incl_vat('corporate', num_days)

            num_tickets = {
                'individual': 0,
                'corporate': 0,
            }

            for ticket in tickets:
                if sum(getattr(ticket, day) for day in DAYS) == num_days:
                    num_tickets[ticket.order.rate] += 1

            num_tickets_rows.append([
                num_days,
                num_tickets['individual'],
                num_tickets['corporate'],
                num_tickets['individual'] + num_tickets['corporate'],
            ])

            ticket_cost_rows.append([
                num_days,
                f'£{num_tickets["individual"] * individual_rate}',
                f'£{num_tickets["corporate"] * corporate_rate}',
                f'£{num_tickets["individual"] * individual_rate + num_tickets["corporate"] * corporate_rate}',
            ])

        return {
            'title': self.title,
            'headings': ['Days', 'Individual rate', 'Corporate rate', 'Total'],
            'num_tickets_rows': num_tickets_rows,
            'ticket_cost_rows': ticket_cost_rows,
        }


class OrdersMixin:
    headings = ['ID', 'Rate', 'Purchaser', 'Email', 'Tickets', 'Cost (incl. VAT)', 'Status']

    def presenter(self, order):
        return [
            order.order_id,
            order.rate,
            order.purchaser.name,
            order.purchaser.email_addr,
            order.num_tickets(),
            f'£{order.cost_incl_vat()}',
            order.status,
        ]


class OrdersReport(ReportView, OrdersMixin):
    title = 'All orders'

    def get_queryset(self):
        return Order.objects.all()


class UnpaidOrdersReport(ReportView, OrdersMixin):
    title = 'Unpaid orders'

    def get_queryset(self):
        return Order.objects.exclude(status='successful')


class TicketsMixin:
    headings = ['ID', 'Rate', 'Ticket holder', 'Days', 'Cost (incl. VAT)', 'Status']

    def presenter(self, ticket):
        return [
            ticket.ticket_id,
            ticket.order.rate,
            ticket.ticket_holder_name(),
            ', '.join(ticket.days()),
            f'£{ticket.cost_incl_vat()}',
            'Assigned' if ticket.owner else 'Unclaimed',
        ]


class TicketsReport(ReportView, TicketsMixin):
    title = 'All tickets'

    def get_queryset(self):
        return Ticket.objects.all()


class UnclaimedTicketsReport(ReportView, TicketsMixin):
    title = 'Unclaimed tickets'

    def get_queryset(self):
        return Ticket.objects.filter(owner=None)


class CFPSubmissionsReport(ReportView):
    title = 'CFP Submissions'

    headings = [
        'ID',
        'Title',
        'Type',
        'Proposer',
        'New programmers?',
        'Teachers?',
        'Data scientists?',
        'Mentor?',
        'Longer slot?',
    ]

    def get_queryset(self):
        return Proposal.objects.all()

    def presenter(self, proposal):
        return [
            proposal.proposal_id,
            proposal.full_title(),
            proposal.session_type,
            proposal.proposer.name,
            '✔' if proposal.aimed_at_new_programmers else '✘',
            '✔' if proposal.aimed_at_teachers else '✘',
            '✔' if proposal.aimed_at_data_scientists else '✘',
            '✔' if proposal.would_like_mentor else '✘',
            '✔' if proposal.would_like_longer_slot else '✘',
        ]


reports = [
    AttendanceByDayReport,
    TicketSalesReport,
    OrdersReport,
    UnpaidOrdersReport,
    TicketsReport,
    UnclaimedTicketsReport,
    CFPSubmissionsReport,
]


@staff_member_required(login_url='login')
def index(request):
    return render(request, 'reports/index.html', {'reports': reports})
