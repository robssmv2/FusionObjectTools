import adsk.core
import adsk.fusion
import json
from pathlib import Path
import re
import traceback


_app = None
_ui = None
_palette = None
_handlers = []
_dissolve_commands = {}

_PALETTE_ID = 'ObjectTypeInspectorPalette'
_PALETTE_NAME = 'Object Type Inspector'
_DISSOLVE_ID = 'ObjectTypeInspectorDissolveAll'
_DISSOLVE_PANEL_ID = 'SolidModifyPanel'
_PLASTIC_PATTERN = re.compile(
    r'\b(plastic|abs|acrylic|nylon|polycarbonate|polyethylene|'
    r'polypropylene|polystyrene|polyurethane|pvc|ptfe|peek|petg|'
    r'pla|pbt|pom|acetal)\b',
    re.IGNORECASE
)


def _object_name(entity):
    name = getattr(entity, 'name', None)
    if name:
        return name
    return entity.objectType.split('::')[-1]


def _material_info(body):
    material = getattr(body, 'material', None)
    if not material:
        return None

    name = material.name
    if not name:
        return None

    is_plastic = bool(_PLASTIC_PATTERN.search(name))
    return {'name': name, 'isPlastic': is_plastic}


def _body_info(body):
    body_name = _object_name(body)

    tspline_body = adsk.fusion.TSplineBody.cast(body)
    if tspline_body:
        category = 'Form (T-Spline)'
    else:
        mesh_body = adsk.fusion.MeshBody.cast(body)
        if mesh_body:
            category = 'Mesh'
        else:
            brep_body = adsk.fusion.BRepBody.cast(body)
            if not brep_body:
                return {
                    'name': body_name,
                    'category': 'Unknown body type',
                    'material': None
                }
            if brep_body.isSheetMetal:
                category = 'Sheet Metal'
            elif brep_body.isSolid:
                category = 'Solid'
            else:
                category = 'Surface'

    material = _material_info(body)
    return {
        'name': body_name,
        'category': category,
        'material': material
    }


def _selected_body(entity):
    for body_type in (
        adsk.fusion.BRepBody,
        adsk.fusion.MeshBody,
        adsk.fusion.TSplineBody
    ):
        body = body_type.cast(entity)
        if body:
            return body

    for entity_type in (
        adsk.fusion.BRepFace,
        adsk.fusion.BRepEdge,
        adsk.fusion.BRepVertex
    ):
        sub_entity = entity_type.cast(entity)
        if sub_entity:
            return sub_entity.body

    return None


def _component_bodies(component):
    bodies = list(component.bRepBodies)
    bodies.extend(component.meshBodies)
    for form in component.features.formFeatures:
        bodies.extend(form.tSplineBodies)
    return bodies


def _component_diagnostics(component):
    return {
        'name': component.name,
        'bRepBodyCount': component.bRepBodies.count,
        'meshBodyCount': component.meshBodies.count,
        'formFeatures': [
            {'name': form.name, 'tSplineBodyCount': form.tSplineBodies.count}
            for form in component.features.formFeatures
        ],
        'featureTypes': [feature.objectType for feature in component.features],
        'children': [
            _component_diagnostics(occurrence.component)
            for occurrence in component.occurrences
        ]
    }


def _describe_selection(entity):
    body = _selected_body(entity)
    if body:
        return {
            'name': _object_name(body),
            'categories': [_body_info(body)],
            'selectionType': _object_name(entity)
        }

    form = adsk.fusion.FormFeature.cast(entity)
    if form:
        return {
            'name': _object_name(form),
            'categories': [_body_info(body) for body in form.tSplineBodies],
            'selectionType': 'Form feature'
        }

    component = adsk.fusion.Component.cast(entity)
    if not component:
        occurrence = adsk.fusion.Occurrence.cast(entity)
        if occurrence:
            component = occurrence.component

    if component:
        categories = [_body_info(body) for body in _component_bodies(component)]
        return {
            'name': _object_name(component),
            'categories': categories,
            'selectionType': 'Component',
            'componentDiagnostics': _component_diagnostics(component)
        }

    return {
        'name': _object_name(entity),
        'categories': [],
        'selectionType': 'Other object'
    }


def _current_selection_data(selections):
    items = []
    api_types = []
    for selection in selections:
        entity = selection.entity
        if entity:
            api_types.append(entity.objectType)
            items.append(_describe_selection(entity))
    return {
        'items': items,
        'diagnostics': {
            'activeCommand': _ui.activeCommand,
            'selectionCount': len(items),
            'apiTypes': api_types,
            'components': [
                item['componentDiagnostics']
                for item in items if 'componentDiagnostics' in item
            ]
        }
    }


def _send_selection(selections):
    if _palette:
        _palette.sendInfoToHTML('selectionChanged', json.dumps(
            _current_selection_data(selections)
        ))


def _show_error(title):
    if _ui:
        _ui.messageBox(traceback.format_exc(), title)


class _SelectionChangedHandler(adsk.core.ActiveSelectionEventHandler):
    def notify(self, event_args):
        try:
            args = adsk.core.ActiveSelectionEventArgs.cast(event_args)
            _send_selection(args.currentSelection)
        except:
            _show_error('Object Type Inspector')


class _PaletteHtmlHandler(adsk.core.HTMLEventHandler):
    def notify(self, event_args):
        try:
            args = adsk.core.HTMLEventArgs.cast(event_args)
            if args.action in ('ready', 'refresh'):
                _send_selection(_ui.activeSelections)
        except:
            _show_error('Object Type Inspector')


def _dissolve_plan(design, include_base_features=False):
    pending = [design.rootComponent]
    visited = []
    candidates = []
    skipped = 0
    linked = 0
    while pending:
        component = pending.pop()
        if component in visited:
            continue
        visited.append(component)
        for occurrence in component.occurrences:
            if occurrence.isReferencedComponent:
                linked += 1
            else:
                pending.append(occurrence.component)
        for feature in reversed(list(component.features)):
            if (feature.isParametric
                    or adsk.fusion.FormFeature.cast(feature)
                    or (adsk.fusion.BaseFeature.cast(feature) and not include_base_features)
                    or feature.bodies.count == 0):
                skipped += 1
                continue
            candidates.append((feature, component.name + ' / ' + feature.name))
    return candidates, skipped, linked


def _dissolve_features(candidates):
    dissolved = 0
    invalidated = 0
    for feature, label in candidates:
        if not feature.isValid:
            invalidated += 1
            continue
        try:
            if not feature.dissolve():
                raise RuntimeError('Fusion returned false from Feature.dissolve().')
        except Exception as error:
            raise RuntimeError('Could not dissolve ' + label + ': ' + str(error)) from error
        dissolved += 1
    return dissolved, invalidated


class _DissolveExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, design, inputs):
        super().__init__()
        self.design = design
        self.inputs = inputs

    def notify(self, event_args):
        args = adsk.core.CommandEventArgs.cast(event_args)
        try:
            if adsk.fusion.Design.cast(_app.activeProduct) != self.design:
                raise RuntimeError('The active design changed. Run Dissolve All again.')
            include_base = self.inputs.itemById('includeBaseFeatures').value
            candidates, skipped, linked = _dissolve_plan(self.design, include_base)
            dissolved, invalidated = _dissolve_features(candidates)
            _ui.messageBox(
                'Dissolved features: {}\n'
                'Features already removed by another dissolve: {}\n'
                'Protected or ineligible features skipped: {}\n'
                'Linked occurrences excluded: {}'.format(
                    dissolved, invalidated, skipped, linked
                ),
                'Dissolve All'
            )
        except Exception:
            args.executeFailed = True
            args.executeFailedMessage = traceback.format_exc()


class _DissolveDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, key):
        super().__init__()
        self.key = key

    def notify(self, event_args):
        _dissolve_commands.pop(self.key, None)


class _DissolveCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, event_args):
        try:
            command = event_args.command
            command.isRepeatable = False
            command.isExecutedWhenPreEmpted = False
            # Never modify the design from command creation or preview.
            command.isAutoExecute = False
            design = adsk.fusion.Design.cast(_app.activeProduct)
            if not design:
                raise RuntimeError('Open a Fusion design before running Dissolve All.')
            candidates, skipped, linked = _dissolve_plan(design)
            expanded_candidates, _, _ = _dissolve_plan(design, include_base_features=True)
            command.commandInputs.addTextBoxCommandInput(
                'dissolveWarning', '',
                'Dissolve eligible non-parametric B-Rep features across the entire '
                'active design, including nested local components?\n\n'
                'Eligible features: {} normally; {} with Base Features included.\n\n'
                'This removes editable feature information but retains B-Rep geometry. '
                'Save a separate copy first.\n\n'
                'Base Features are excluded unless enabled below. Including them '
                'also removes their editable source grouping.\n\n'
                'Parametric features, Forms, features without B-Rep bodies, '
                'and linked external components are always excluded. '
                'Design history will not be switched off.\n\n'
                'Click OK to dissolve, or Cancel to leave the model unchanged.'.format(
                    len(candidates), len(expanded_candidates)
                ),
                12, True
            )
            command.commandInputs.addBoolValueInput(
                'includeBaseFeatures', 'Include Base Features (B-Rep)', True, '', False
            )
            execute = _DissolveExecuteHandler(design, command.commandInputs)
            destroy = _DissolveDestroyHandler(id(command))
            _dissolve_commands[id(command)] = (execute, destroy)
            if not command.execute.add(execute) or not command.destroy.add(destroy):
                raise RuntimeError('Could not attach Dissolve All command handlers.')
        except Exception:
            _show_error('Dissolve All could not start')


def _install_dissolve_command():
    workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
    panel = workspace.toolbarPanels.itemById(_DISSOLVE_PANEL_ID) if workspace else None
    if not panel:
        raise RuntimeError('Could not find the Design workspace Modify panel.')
    definition = _ui.commandDefinitions.itemById(_DISSOLVE_ID)
    if not definition:
        definition = _ui.commandDefinitions.addButtonDefinition(
            _DISSOLVE_ID, 'Dissolve All',
            'Dissolve non-parametric B-Rep features throughout the active design; '
            'preserve geometry and protect Forms.'
        )
    handler = _DissolveCreatedHandler()
    if not definition.commandCreated.add(handler):
        raise RuntimeError('Could not register Dissolve All.')
    _handlers.append((definition.commandCreated, handler))
    if not panel.controls.itemById(_DISSOLVE_ID):
        if not panel.controls.addCommand(definition):
            raise RuntimeError('Could not add Dissolve All to the Modify menu.')


def run(context):
    global _app, _ui, _palette
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface

        palettes = _ui.palettes
        _palette = palettes.itemById(_PALETTE_ID)
        if not _palette:
            html_url = Path(__file__).resolve().with_name('index.html').as_uri()
            _palette = palettes.add(
                _PALETTE_ID,
                _PALETTE_NAME,
                html_url,
                True,
                True,
                True,
                320,
                260,
                True
            )
        if not _palette:
            raise RuntimeError('Fusion could not create the inspector palette.')

        selection_handler = _SelectionChangedHandler()
        if not _ui.activeSelectionChanged.add(selection_handler):
            raise RuntimeError('Could not subscribe to Fusion selection changes.')
        _handlers.append((_ui.activeSelectionChanged, selection_handler))

        html_handler = _PaletteHtmlHandler()
        if not _palette.incomingFromHTML.add(html_handler):
            raise RuntimeError('Could not subscribe to inspector palette events.')
        _handlers.append((_palette.incomingFromHTML, html_handler))

        _install_dissolve_command()
        _send_selection(_ui.activeSelections)
    except:
        _show_error('Object Type Inspector failed to start')


def stop(context):
    global _palette, _ui, _app
    errors = []
    for event, handler in reversed(_handlers):
        try:
            if not event.remove(handler):
                errors.append('Fusion could not remove an event handler.')
        except:
            errors.append(traceback.format_exc())
    _handlers.clear()

    if _ui:
        try:
            workspace = _ui.workspaces.itemById('FusionSolidEnvironment')
            panel = workspace.toolbarPanels.itemById(_DISSOLVE_PANEL_ID) if workspace else None
            control = panel.controls.itemById(_DISSOLVE_ID) if panel else None
            if control and not control.deleteMe():
                errors.append('Could not remove the Dissolve All menu item.')
            definition = _ui.commandDefinitions.itemById(_DISSOLVE_ID)
            if definition and not definition.deleteMe():
                errors.append('Could not remove the Dissolve All command.')
        except Exception:
            errors.append(traceback.format_exc())

    if _palette:
        try:
            if not _palette.deleteMe():
                errors.append('Fusion could not close the inspector palette.')
        except:
            errors.append(traceback.format_exc())

    if errors and _ui:
        _ui.messageBox('\n'.join(errors), 'Object Type Inspector failed to stop')

    _palette = None
    _ui = None
    _app = None
