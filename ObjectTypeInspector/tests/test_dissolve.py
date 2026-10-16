import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class ApiType:
    @classmethod
    def cast(cls, value):
        return value if isinstance(value, cls) else None


class Collection(list):
    @property
    def count(self):
        return len(self)


class Feature(ApiType):
    def __init__(self, name='Extrude', parametric=False, bodies=1):
        self.name = name
        self.isParametric = parametric
        self.bodies = Collection([object() for _ in range(bodies)])
        self.isValid = True
        self.dissolve = Mock(return_value=True)


class FormFeature(Feature):
    pass


class BaseFeature(Feature):
    pass


class Design(ApiType):
    pass


def load_inspector():
    adsk = ModuleType('adsk')
    adsk.__path__ = []
    core = ModuleType('adsk.core')
    fusion = ModuleType('adsk.fusion')
    for name in ('ActiveSelectionEventHandler', 'HTMLEventHandler',
                 'CommandEventHandler', 'CommandCreatedEventHandler'):
        setattr(core, name, type(name, (), {}))
    core.CommandEventArgs = SimpleNamespace(cast=lambda args: args)
    fusion.FormFeature = FormFeature
    fusion.BaseFeature = BaseFeature
    fusion.Design = Design
    adsk.core, adsk.fusion = core, fusion
    path = Path(__file__).resolve().parents[1] / 'ObjectTypeInspector.py'
    spec = importlib.util.spec_from_file_location('inspector_under_test', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        'adsk': adsk, 'adsk.core': core, 'adsk.fusion': fusion
    }):
        spec.loader.exec_module(module)
    return module


def component(name, features=(), children=()):
    return SimpleNamespace(
        name=name, features=Collection(features), occurrences=list(children)
    )


def occurrence(comp, linked=False):
    return SimpleNamespace(component=comp, isReferencedComponent=linked)


def inputs(include_base=False):
    return SimpleNamespace(
        itemById=lambda name: SimpleNamespace(value=include_base)
    )


class DissolveTests(unittest.TestCase):
    def setUp(self):
        self.inspector = load_inspector()

    def test_entire_design_unique_components_reverse_feature_order_and_links(self):
        first, last, nested = Feature('First'), Feature('Last'), Feature('Nested')
        external_feature = Feature('External')
        child = component('Child', [nested])
        external = component('External', [external_feature])
        root = component('Root', [first, last], [
            occurrence(child), occurrence(child), occurrence(external, linked=True)
        ])
        candidates, skipped, linked = self.inspector._dissolve_plan(
            SimpleNamespace(rootComponent=root)
        )
        self.assertEqual([feature for feature, _ in candidates], [last, first, nested])
        self.assertEqual((skipped, linked), (0, 1))
        external_feature.dissolve.assert_not_called()

    def test_protects_parametric_form_base_and_non_brep_features(self):
        safe = Feature()
        root = component('Root', [
            Feature(parametric=True), FormFeature(), BaseFeature(),
            Feature(bodies=0), safe
        ])
        candidates, skipped, _ = self.inspector._dissolve_plan(
            SimpleNamespace(rootComponent=root)
        )
        self.assertEqual(candidates, [(safe, 'Root / Extrude')])
        self.assertEqual(skipped, 4)
        safe.dissolve.assert_not_called()

    def test_dissolves_and_skips_invalidated_features(self):
        feature, invalid = Feature(), Feature()
        invalid.isValid = False
        self.assertEqual(
            self.inspector._dissolve_features([(feature, 'A'), (invalid, 'B')]),
            (1, 1)
        )
        feature.dissolve.assert_called_once_with()
        invalid.dissolve.assert_not_called()

    def test_base_option_preserves_form_parametric_and_bodyless_protections(self):
        base = BaseFeature()
        root = component('Root', [
            base, BaseFeature(parametric=True), BaseFeature(bodies=0), FormFeature()
        ])
        design = SimpleNamespace(rootComponent=root)
        self.assertEqual(self.inspector._dissolve_plan(design)[0], [])
        candidates, skipped, _ = self.inspector._dissolve_plan(design, True)
        self.assertEqual(candidates, [(base, 'Root / Extrude')])
        self.assertEqual(skipped, 3)

    def test_execute_uses_checkbox_value(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                base = BaseFeature()
                design = Design()
                design.rootComponent = component('Root', [base])
                self.inspector._app = SimpleNamespace(activeProduct=design)
                self.inspector._ui = SimpleNamespace(messageBox=Mock())
                args = SimpleNamespace(executeFailed=False)
                self.inspector._DissolveExecuteHandler(
                    design, inputs(enabled)
                ).notify(args)
                self.assertFalse(args.executeFailed)
                self.assertEqual(base.dissolve.call_count, int(enabled))

    def test_false_or_exception_stops_without_processing_later_features(self):
        for outcome in (False, RuntimeError('API failure')):
            with self.subTest(outcome=outcome):
                bad, later = Feature(), Feature()
                if isinstance(outcome, Exception):
                    bad.dissolve.side_effect = outcome
                else:
                    bad.dissolve.return_value = outcome
                with self.assertRaisesRegex(RuntimeError, 'Root / Bad'):
                    self.inspector._dissolve_features([
                        (bad, 'Root / Bad'), (later, 'Root / Later')
                    ])
                later.dissolve.assert_not_called()

    def test_execute_marks_transaction_failed_on_error(self):
        design = Design()
        self.inspector._app = SimpleNamespace(activeProduct=design)
        bad = Feature()
        bad.dissolve.return_value = False
        bad.name = 'Bad'
        design.rootComponent = component('Root', [bad])
        args = SimpleNamespace(executeFailed=False, executeFailedMessage='')
        handler = self.inspector._DissolveExecuteHandler(
            design, inputs()
        )
        handler.notify(args)
        self.assertTrue(args.executeFailed)
        self.assertIn('Root / Bad', args.executeFailedMessage)

    def test_changed_design_prevents_modification(self):
        self.inspector._app = SimpleNamespace(activeProduct=Design())
        feature = Feature()
        args = SimpleNamespace(executeFailed=False, executeFailedMessage='')
        self.inspector._DissolveExecuteHandler(
            Design(), inputs()
        ).notify(args)
        self.assertTrue(args.executeFailed)
        feature.dissolve.assert_not_called()

    def test_command_creation_only_prepares_confirmation(self):
        feature = Feature()
        design = Design()
        design.rootComponent = component('Root', [feature])
        self.inspector._app = SimpleNamespace(activeProduct=design)
        command = SimpleNamespace(
            commandInputs=Mock(),
            execute=SimpleNamespace(add=Mock(return_value=True)),
            destroy=SimpleNamespace(add=Mock(return_value=True))
        )
        self.inspector._DissolveCreatedHandler().notify(
            SimpleNamespace(command=command)
        )
        self.assertFalse(command.isAutoExecute)
        self.assertFalse(command.isExecutedWhenPreEmpted)
        self.assertFalse(command.isRepeatable)
        command.commandInputs.addTextBoxCommandInput.assert_called_once()
        command.commandInputs.addBoolValueInput.assert_called_once_with(
            'includeBaseFeatures', 'Include Base Features (B-Rep)', True, '', False
        )
        feature.dissolve.assert_not_called()
        execute, destroy = self.inspector._dissolve_commands[id(command)]
        self.assertIsInstance(execute, self.inspector._DissolveExecuteHandler)
        destroy.notify(SimpleNamespace())
        self.assertNotIn(id(command), self.inspector._dissolve_commands)

    def test_success_reports_counts(self):
        design = Design()
        design.rootComponent = component('Root', [
            Feature(), FormFeature(), BaseFeature()
        ], [occurrence(component('External'), linked=True)])
        self.inspector._app = SimpleNamespace(activeProduct=design)
        self.inspector._ui = SimpleNamespace(messageBox=Mock())
        args = SimpleNamespace(executeFailed=False)
        self.inspector._DissolveExecuteHandler(
            design, inputs()
        ).notify(args)
        self.assertFalse(args.executeFailed)
        message = self.inspector._ui.messageBox.call_args.args[0]
        self.assertIn('Dissolved features: 1', message)
        self.assertIn('features skipped: 2', message)
        self.assertIn('Linked occurrences excluded: 1', message)


if __name__ == '__main__':
    unittest.main()
