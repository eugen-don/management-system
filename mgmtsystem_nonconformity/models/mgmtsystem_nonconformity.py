# -*- coding: utf-8 -*-
# Copyright 2012 Savoir-faire Linux <http://www.savoirfairelinux.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api, fields, exceptions, _
from datetime import datetime, timedelta


class MgmtsystemNonconformity(models.Model):

    _name = "mgmtsystem.nonconformity"
    _description = "Nonconformity"
    _rec_name = "name"
    _inherit = ['mail.thread']
    _order = "create_date desc"
    _track = {
        'field': {
            'mgmtsystem_nonconformity.subtype_analysis': (
                lambda s, c, u, o, ctx=None:
                    o["stage_id"] == "mgmtsystem_nonconformity.stage_draft"
            ),
            'mgmtsystem_nonconformity.subtype_pending': (
                lambda s, c, u, o, ctx=None:
                    o["stage_id"] == "mgmtsystem_nonconformity.stage_pending"
            ),
        },
    }

    @api.model
    def _default_stage(self):
        """Return the default stage."""
        return (
            self.env.ref('mgmtsystem_nonconformity.stage_draft', False) or
            self.env['mgmtsystem.nonconformity.stage'].search(
                [('is_starting', '=', True)],
                limit=1))

    @api.model
    def _stage_groups(self, stages, domain, order):
        stage_ids = self.env['mgmtsystem.nonconformity.stage'].search([])
        return stage_ids

    name = fields.Char('Name')
    number_of_nonconformities = fields.Integer(
        '# of nonconformities', readonly=True, default=1)
    ref = fields.Char(
        'Reference',
        required=True,
        readonly=True,
        default="NEW"
    )
    date_deadline = fields.Datetime('Deadline', readonly=False,
                                    default=fields.Datetime.now())
    create_date = fields.Datetime('Create Date', readonly=True,
                                  default=fields.Datetime.now())
    number_of_nonconformities = fields.Integer(
        '# of nonconformities', readonly=True, default=1)
    days_since_updated = fields.Integer(
        readonly=True,
        compute='_compute_days_since_updated',
        store=True)
    number_of_days_to_close = fields.Integer(
        '# of days to close',
        compute='_compute_number_of_days_to_close',
        store=True,
        readonly=True)
    closing_date = fields.Datetime(
        'Closing Date',
        readonly=True,
        default=lambda self: fields.Datetime.now())
    cancel_date = fields.Datetime('Cancel Date', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Partner', required=False)
    reference = fields.Char('Related to')
    responsible_user_id = fields.Many2one(
        'res.users',
        'Responsible',
        required=True,
    )
    manager_user_id = fields.Many2one(
        'res.users',
        'Manager',
        required=True,
    )
    user_id = fields.Many2one(
        'res.users',
        'Filled in by',
        required=True,
        default=lambda self: self.env.user,
        track_visibility=True,
    )
    author_user_id = fields.Many2one(
        'res.users',
        'Filled in by',
        required=True,
        default=lambda self: self.env.user,
        track_visibility=True
    )
    origin_ids = fields.Many2many(
        'mgmtsystem.nonconformity.origin',
        'mgmtsystem_nonconformity_origin_rel',
        'nonconformity_id',
        'origin_id',
        'Origin',
        required=True,
    )
    procedure_ids = fields.Many2many(
        'document.page',
        'mgmtsystem_nonconformity_procedure_rel',
        'nonconformity_id',
        'procedure_id',
        'Procedure',
    )
    description = fields.Text('Description', required=True)

    system_id = fields.Many2one('mgmtsystem.system', 'System')

    stage_id = fields.Many2one(
        'mgmtsystem.nonconformity.stage',
        'Stage',
        track_visibility='onchange', index=True,
        copy=False,
        default=_default_stage, group_expand='_stage_groups')

    state = fields.Selection(
        related='stage_id.state',
        store=True,
    )
    kanban_state = fields.Selection(
        [('normal', 'In Progress'),
         ('done', 'Ready for next stage'),
         ('blocked', 'Blocked')],
        'Kanban State',
        default='normal',
        track_visibility='onchange', index=True,
        help="A kanban state indicates special situations affecting it:\n"
        " * Normal is the default situation\n"
        " * Blocked indicates something is preventing"
        " the progress of this task\n"
        " * Ready for next stage indicates the"
        " task is ready to be pulled to the next stage",
        required=True, copy=False)

    # 2. Root Cause Analysis
    cause_ids = fields.Many2many(
        'mgmtsystem.nonconformity.cause',
        'mgmtsystem_nonconformity_cause_rel',
        'nonconformity_id',
        'cause_id',
        'Cause',
    )
    severity_id = fields.Many2one(
        'mgmtsystem.nonconformity.severity',
        'Severity',
    )
    priority = fields.Selection([
            ('0', 'Low'),
            ('1', 'Normal'),
            ('2', 'High')
        ], default='0', index=True)
    analysis = fields.Text('Analysis')
    immediate_action_id = fields.Many2one(
        'mgmtsystem.action',
        'Immediate action',
        domain="[('nonconformity_ids', '=', id)]",
    )
    # 3. Action Plan
    action_ids = fields.Many2many(
        'mgmtsystem.action',
        'mgmtsystem_nonconformity_action_rel',
        'nonconformity_id',
        'action_id',
        'Actions',
    )
    action_comments = fields.Text(
        'Action Plan Comments',
        help="Comments on the action plan.",
    )
    evaluation_comments = fields.Text(
        'Evaluation Comments',
        help="Conclusions from the last effectiveness evaluation.",
    )

    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        'Company',
        default=lambda self: self.env.user.company_id.id)

    # Demo data missing fields...
    corrective_action_id = fields.Many2one(
        'mgmtsystem.action',
        'Corrective action',
        domain="[('nonconformity_id', '=', id)]",
    )
    preventive_action_id = fields.Many2one(
        'mgmtsystem.action',
        'Preventive action',
        domain="[('nonconformity_id', '=', id)]",
    )

    @api.multi
    def _track_template(self, tracking):
        self.ensure_one()
        res = super(MgmtsystemNonconformity, self)._track_template(tracking)
        changes, dummy = tracking[self.id]
        if 'stage_id' in changes and self.stage_id.mail_template_id:
            res['stage_id'] = (
                self.stage_id.mail_template_id,
                {'composition_mode': 'mass_mail'})
        return res

    @api.multi
    def _get_all_actions(self):
        self.ensure_one()
        return (self.action_ids +
                self.corrective_action_id +
                self.preventive_action_id)

    @api.constrains('stage_id')
    def _check_open_with_action_comments(self):
        for nc in self:
            if nc.state == 'open' and not nc.action_comments:
                raise exceptions.ValidationError(
                    _("Action plan  comments are required "
                      "in order to put a nonconformity In Progress."))

    @api.constrains('stage_id')
    def _check_close_with_evaluation(self):
        for nc in self:
            if nc.state == 'done':
                if not nc.evaluation_comments:
                    raise exceptions.ValidationError(
                        _("Evaluation Comments are required "
                          "in order to close a Nonconformity."))
                actions_are_closed = (
                    x.stage_id.is_ending
                    for x in nc._get_all_actions())
                if not all(actions_are_closed):
                    raise exceptions.ValidationError(
                        _("All actions must be done "
                          "before closing a Nonconformity."))

    @api.model
    def _elapsed_days(self, dt1_text, dt2_text):
        res = 0
        if dt1_text and dt2_text:
            dt1 = fields.Datetime.from_string(dt1_text)
            dt2 = fields.Datetime.from_string(dt2_text)
            res = (dt2 - dt1).days
        return res

    @api.depends('write_date')
    def _compute_days_since_updated(self):
        for nc in self:
            nc.days_since_updated = self._elapsed_days(
                nc.create_date,
                nc.write_date)

    @api.model
    def create(self, vals):
        vals.update({
            'ref': self.env['ir.sequence'].next_by_code(
                'mgmtsystem.nonconformity')
        })
        return super(MgmtsystemNonconformity, self).create(vals)

    @api.multi
    def write(self, vals):
        is_writing = 'is_writing' in self.env.context
        is_state_change = 'stage_id' in vals or 'state' in vals
        # Reset Kanban State on Stage change
        if is_state_change:
            was_not_open = {
                x.id: x.state in ('draft',
                                  'analysis', 'pending') for x in self}
            for nc in self:
                if nc.kanban_state != 'normal':
                    vals['kanban_state'] = 'normal'

        result = super(MgmtsystemNonconformity, self).write(vals)

        # Set/reset the closing date
        if not is_writing and is_state_change:
            for nc in self.with_context(is_writing=True):
                # On Close set Closing Date
                if nc.state == 'done' and not nc.closing_date:
                    nc.closing_date = fields.Datetime.now()
                # On reopen resete Closing Date
                if nc.state != 'done' and nc.closing_date:
                    nc.closing_date = None
                # On action plan approval, Open the Actions
                if nc.state == 'open' and was_not_open[nc.id]:
                    for action in nc._get_all_actions():
                        if action.stage_id.is_starting:
                            action.case_open()
        return result

    # method returns url of NC
    def get_nonconformity_url(self):
        """Return nonconformity url to be used in email templates."""
        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url',
            default='http://localhost:8069'
        )
        url = ('{}/web#db={}&id={}&model={}').format(
            base_url,
            self.env.cr.dbname,
            self.id,
            self._name
        )
        return url

    @api.model
    def process_nonconformity_reminder_queue(self, reminder_days=10):
        """Notify user when we are 10 days close to a deadline."""
        cur_date = datetime.now().date() + timedelta(days=reminder_days)
        stage_close = self.env.ref('mgmtsystem_nonconformity.stage_close')
        nonconformity_ids = self.search(
            [("stage_id", "!=", stage_close.id),
             ("action_ids.stage_id", "!=", stage_close.id),
             ("date_deadline", "=", cur_date),
             ])
        template = self.env.ref(
            'mgmtsystem_nonconformity.nonconformity_email_template_reminder')
        for nonconformity in nonconformity_ids:
            template.send_mail(nonconformity.id, force_send=True)
        return True
