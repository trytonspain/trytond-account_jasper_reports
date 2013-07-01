#This file is part of account_jasper_reports for tryton.  The COPYRIGHT file
#at the top level of this repository contains the full copyright notices and
#license terms.
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.pyson import Eval, Bool
from trytond.modules.jasper_reports.jasper import JasperReport

__all__ = ['PrintJournalStart', 'PrintJournal', 'JournalReport']


class PrintJournalStart(ModelView):
    'Print Journal'
    __name__ = 'account_jasper_reports.print_journal.start'
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
            required=True, on_change=['fiscalyear'])
    start_period = fields.Many2One('account.period', 'Start Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
            ], depends=['fiscalyear', 'end_period'])
    end_period = fields.Many2One('account.period', 'End Period',
        domain=[
            ('fiscalyear', '=', Eval('fiscalyear')),
            ('start_date', '>=', (Eval('start_period'), 'start_date'))
            ],
        depends=['fiscalyear', 'start_period'])
    all_journals = fields.Boolean('All Journals')
    journals = fields.Many2Many('account.journal', None, None, 'Journals',
        states={
            'invisible': Bool(Eval('all_journals')),
            'required': ~Bool(Eval('all_journals')),
            }, depends=['all_journals'])
    output_type = fields.Selection([
            ('pdf', 'PDF'),
            ('xls', 'XLS'),
            ], 'Output Type', required=True)
    company = fields.Many2One('company.company', 'Company', required=True)

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_all_journals():
        return True

    @staticmethod
    def default_output_type():
        return 'pdf'

    def on_change_fiscalyear(self):
        return {
            'start_period': None,
            'end_period': None,
            }

class PrintJournal(Wizard):
    'Print Journal'
    __name__ = 'account_jasper_reports.print_journal'
    start = StateView('account_jasper_reports.print_journal.start',
        'account_jasper_reports.print_journal_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateAction('account_jasper_reports.report_journal')

    def do_print_(self, action):
        start_period = None
        if self.start.start_period:
            start_period = self.start.start_period.id
        end_period = None
        if self.start.end_period:
            end_period = self.start.end_period.id
        data = {
            'company': self.start.company.id,
            'fiscalyear': self.start.fiscalyear.id,
            'start_period': start_period,
            'end_period': end_period,
            'journals': [x.id for x in self.start.journals],
            'output_type': self.start.output_type,
            'all_journals': self.start.all_journals,
            }
        print "action:",action
        print "data:", data
        return action, data

    def transition_print_(self):
        return 'end'

class JournalReport(JasperReport):
    __name__ = 'account_jasper_reports.journal'

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Journal = pool.get('account.journal')
        Period = pool.get('account.period')
        Line = pool.get('account.move.line')
        parameters = {}
        fiscalyear = FiscalYear(data['fiscalyear'])
        start_period = None
        if data['start_period']:
            start_period = Period(data['start_period'])
        end_period = None
        if data['end_period']:
            end_period = Period(data['end_period'])
        journals = Journal.browse(data.get('journals', []))

        parameters['start_period'] = start_period and start_period.name or ''
        parameters['end_period'] = end_period and end_period.name or ''
        parameters['fiscal_year'] = fiscalyear.name
        if journals:
            parameters['journals'] = ','.join([str(x.name) for x in journals])
        else:
            parameters['journals'] = ''

        if journals:
            journals = ','.join([str(x.id) for x in journals])
            journals = 'am.journal IN (%s) AND' % journals
        else:
            journals = ''

        periods = fiscalyear.get_periods(start_period, end_period)
        if periods:
            periods = ','.join([str(x.id) for x in periods])
            periods = 'am.period IN (%s) AND' % periods
        else:
            periods = ''

        cursor = Transaction().cursor
        cursor.execute("""
            SELECT
                aml.id
            FROM
                account_move am,
                account_move_line aml
            WHERE
                %s
                %s
                am.id=aml.move
            ORDER BY
                am.date, am.number, aml.id
        """ % (
                journals,
                periods,
                ))
        ids = [x[0] for x in cursor.fetchall()]
        # Pass through access rights and rules
        ids = [x.id for x in Line.browse(ids)]
        return super(JournalReport, cls).execute(ids, {
                'name': 'account_jasper_reports.journal',
                'model': 'account.move.line',
                'data_source': 'model',
                'parameters': parameters,
                'output_format': data['output_type'],
                })
