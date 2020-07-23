# This file is part of Indico.
# Copyright (C) 2002 - 2020 CERN
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see the
# LICENSE file for more details.

from __future__ import unicode_literals

import os

from flask import flash, request, session
from werkzeug.exceptions import NotFound

from indico.core.config import config
from indico.modules.events.abstracts.controllers.base import RHAbstractsBase, RHManageAbstractsBase
from indico.modules.events.abstracts.forms import BOASettingsForm
from indico.modules.events.abstracts.settings import boa_settings
from indico.modules.events.abstracts.util import clear_boa_cache, create_boa, create_boa_tex
from indico.modules.events.contributions import contribution_settings
from indico.modules.files.controllers import UploadFileMixin
from indico.util.i18n import _
from indico.util.marshmallow import FileField
from indico.web.args import use_kwargs
from indico.web.flask.util import send_file
from indico.web.forms.base import FormDefaults
from indico.web.util import jsonify_data, jsonify_form


class RHBOASettings(RHManageAbstractsBase):
    """Configure book of abstracts"""

    def _process(self):
        form = BOASettingsForm(obj=FormDefaults(**boa_settings.get_all(self.event)))
        if form.validate_on_submit():
            boa_settings.set_multi(self.event, form.data)
            clear_boa_cache(self.event)
            flash(_('Book of Abstract settings have been saved'), 'success')
            return jsonify_data()
        if self.event.has_custom_boa:
            message = _("You are currently using an uploaded custom book of abstracts PDF. Please note "
                        "that every change in these settings will only change the LaTeX files and "
                        "not the custom PDF, which is the one displayed via the 'Book of Abstracts' "
                        "menu item in the display view.")
            return jsonify_form(form, message=message)
        return jsonify_form(form)


class RHUploadBOAFile(UploadFileMixin, RHManageAbstractsBase):
    def get_file_context(self):
        return 'event', self.event.id, 'boa'


class RHUploadBOA(RHManageAbstractsBase):
    """Upload custom book of abstracts"""

    @use_kwargs({
        'file': FileField(required=True),
    })
    def _process_POST(self, file):
        if os.path.splitext(file.filename)[1] == '.pdf':
            raise Exception('Uploaded book of abstracts needs to be a ".pdf".')
        self.event.custom_boa = file
        file.claim(event_id=self.event.id)
        return '', 204

    def _process_DELETE(self):
        if self.event.custom_boa is not None:
            self.event.custom_boa = None
        return '', 204


class RHExportBOA(RHAbstractsBase):
    """Export the book of abstracts"""

    def _check_access(self):
        RHAbstractsBase._check_access(self)
        published = contribution_settings.get(self.event, 'published')
        if not published:
            raise NotFound(_("The contributions of this event have not been published yet"))

    def _process(self):
        if request.args.get('latex') == '1' and config.LATEX_ENABLED and self.event.can_manage(session.user):
            return send_file('book-of-abstracts.pdf', create_boa(self.event), 'application/pdf')
        if self.event.has_custom_boa:
            return self.event.custom_boa.send()
        elif config.LATEX_ENABLED:
            return send_file('book-of-abstracts.pdf', create_boa(self.event), 'application/pdf')
        raise NotFound


class RHExportBOATeX(RHManageAbstractsBase):
    """Export a zip file with the book of abstracts in TeX format"""

    def _process(self):
        return send_file('book-of-abstracts.zip', create_boa_tex(self.event), 'application/zip', inline=False)
