from tests import AppBase

from app.utils import load_provider


class ProvidersTest(AppBase):

    def test_providers_config(self):
        self.config_param_test('PROVIDERS', list)

        for name in self.app.config['PROVIDERS']:
            self.config_param_test(name.upper(), dict)

    def test_providers_loader(self):
        for name in self.app.config['PROVIDERS']:
            load_provider(self.app, name)

            self.assertIsInstance(self.app.providers, dict)
            self.assertIn(name, self.app.providers)
            self.assertEqual(name, self.app.providers[name].name)

    def test_providers_method_redirect(self):
        for name in self.app.config['PROVIDERS']:
            load_provider(self.app, name)

            provider = self.app.providers[name]
            rv = provider.redirect()
            self.assertIsInstance(rv, str)
            self.assertTrue(rv.startswith('http'))

    def test_providers_method_identity(self):
        pass

    def test_providers_method_fetch(self):
        pass

    def test_providers_method_push(self):
        pass

    def test_providers_method_tokenize(self):
        pass
