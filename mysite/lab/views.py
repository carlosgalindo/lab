from django.shortcuts import render
from django.http import HttpResponse
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from decimal import Decimal
import json

from .models import *

import utils

from rest_framework import viewsets
from .serializers import *

class BrickViewSet(viewsets.ModelViewSet):
    queryset = Brick.objects.all()
    serializer_class = BrickSerializer

def index(request):
    return render(request, 'lab/index.html', dict())

def setup(request):
    import setup_db
    return HttpResponse(setup_db.setup())

def _data(config=None):
    # print '_data', config
    def _all(dbmodel):
        return dbmodel.objects.all()
    def _list(dbmodel):
        return [ config.get(dbmodel) ] if config else _all(dbmodel)
    def _datetime(datetime):
        return str(datetime) if datetime else ''
    def _ext(db1, d2):
        d2.update(id=db1.id, full=str(db1))
        return d2
    def _dict(dbn, fn):
        return dict([ (each.id, _ext(each, fn(each)))
            for each in dbn ])
    """
    data = dict(
        forces = _dict(_list(Force), lambda force: dict(
            name = force.name,
            mgrs = _dict(force.forcemgr_set.all(), lambda mgr: dict(
                reps = _dict(mgr.forcerep_set.all(), lambda rep: dict(
                )),
            )),
        )),
    )
    """
    data = None
    rep = config.get('rep')
    visit = config.get('visit')
    if visit:
        if rep: error
        rep = visit.rep
    if rep:
        forms = _all(Form)
        def _names(rel):
            return ', '.join([ each.name for each in rel.all() ])
        def _visit(visit, ext=False):
            loc = visit.loc
            doc = loc.doctor
            v = dict(
                datetime = _datetime(visit.datetime),
                status = visit.status or '',
                observations = visit.observations,
                doc_name = doc.user.fullname(),
                doc_email = doc.user.email,
                doc_cats = _names(doc.cats),
                doc_specialties = _names(doc.specialties),
                loc_name = loc.name,
                loc_address = '%s # %s, %s' % (loc.street, loc.unit, loc.zip),
                forms = [ form.id for form in forms
                          if force in form.forces.all()
                          or any( [ each for each in markets if each in form.markets.all() ] )
                          or any( [ each for each in [ e.cat for e in markets ] if each in form.marketcats.all() ] )
                          or loc.zip.brick in form.bricks.all()
                          or (loc.loc and loc.loc in form.locs.all())
                          or (loc.loc and loc.loc.cat in form.loccats.all())
                          or any( [ each for each in doc.cats.all() if each in form.doctorcats.all() ] )
                          or any( [ each for each in doc.specialties.all() if each in form.doctorspecialties.all() ] )
                          ],
                rec = visit.rec_dict(),
            )
            if ext:
                _ext(visit, v)
            return v
        # bricks = rep.bricks.all()
        force = rep.mgr.force
        # def _db_ids(q): return [ each.id for each in q.all() ]
        markets = force.markets.all()
        data = _visit(visit, ext=True) if visit else dict(
            visits = _dict(rep.visits(), _visit),
            forms = _dict(forms, lambda form: dict(
                name = form.name,
                fields = _dict(form.formfield_set.all(), lambda field: dict(
                    name = field.name,
                    required = field.required,
                    default = field.default,
                    opts = field.opts(),
                )),
            )),
        )
    # print '_data', config, data
    return data

def agenda(request):
    data = None
    def _dbget(dbmodel, dbid):
        return utils.db_get(dbmodel, dbid)
    scope = request.GET.get('rep')
    if scope: # only rep scope supported for now.
        # print 'agenda > rep scope', scope
        rep = _dbget(ForceRep, scope)
        if rep:
            data = _data(dict(rep=rep))
    return render(request, 'lab/agenda.html', dict(agenda=True, data=json.dumps(data) or 'null'))

def ajax(request):
    pvars = json.loads(request.POST.get('data'), parse_float=Decimal)
    # print 'ajax', pvars
    def _get(key, default=None):
        pv = pvars.get(key)
        # print '_get', key, pv
        return pv or ('' if default is None else default)
    def _dbget(dbmodel, dbid):
        return utils.db_get(dbmodel, dbid)
    def _ref(key, dbmodel):
        pv = _get(key)
        pv = _dbget(dbmodel, pv) if pv else None
        # print 'ajax > _ref', key, dbmodel, pv.id if pv else None, pv
        return pv
    def _get_datetime(key):
        return _get(key) or None
    def _new(dbmodel, **kwargs):
        return dbmodel.objects.create(**kwargs)
    def _int(string):
        try: v = int(string)
        except: v = None
        return v
    def _decimal(string):
        try: v = Decimal(string)
        except: v = None
        return v
    visit = _ref('ref_visit', ForceVisit)
    # print 'ajax', visit
    errors = []
    try:
        with transaction.atomic():
            def _update(_obj, _dbvars):
                # print '_update', _obj, _dbvars
                for dbk, dbv in _dbvars.items():
                    setattr(_obj, dbk, dbv)
                _obj.save()
            rec = visit.rec_dict()
            rec2 = pvars.get('rec')
            if rec2: # could be None.
                # print 'recs', rec, rec2
                rec.update(rec2)
            dbvars = dict(
                # sched = _get_datetime('sched'),
                status = _get('status'),
                observations = _get('observations'),
                rec = json.dumps(rec),
            )
            # print 'dbvars', dbvars
            _update(visit, dbvars)
    except IntegrityError as e:
        errors.append('Not unique, invalid.')
        # raise(e)
    except ValidationError as e:
        # print 'ValidationError @ views.py', e
        errors.append('Validation error:  %s' % '; '.join(e.messages))
        # raise(e)
    data = dict(
        error = ', '.join(errors),
        visit = None if errors else _data(dict(visit=visit)),
    )
    # print 'ajax > data', data
    return HttpResponse(json.dumps(data))




from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

@login_required
def member_index(request):
    return render_to_response("member/member-index.html", RequestContext(request))

@login_required
def member_action(request):
    return render_to_response("member/member-action.html", RequestContext(request))





from django.views.generic.edit import UpdateView
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse_lazy

from .forms import *

class UserEditView(UpdateView):
    """Allow view and update of basic user data.

    In practice this view edits a model, and that model is
    the User object itself, specifically the names that
    a user has.

    The key to updating an existing model, as compared to creating
    a model (i.e. adding a new row to a database) by using the
    Django generic view ``UpdateView``, specifically the
    ``get_object`` method.
    """
    form_class = UserEditForm
    template_name = "auth/profile.html"
    #success_url = '/email-sent/'
    view_name = 'account_profile'
    success_url = reverse_lazy(view_name)

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        # TODO: not sure how to enforce *minimum* length of a field.
        #print "form valid..."
        #print "save to user:", self.request.user, form.cleaned_data
        form.save()
        messages.add_message(self.request, messages.INFO, 'User profile updated')
        return super(UserEditView, self).form_valid(form)

account_profile = login_required(UserEditView.as_view())
