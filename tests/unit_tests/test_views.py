from unittest.mock import Mock, patch

from flask import get_flashed_messages, session, url_for

from app.forms import BaseForm
from app.main.add_a_new_provider.forms import AssignContractManagerForm
from app.main.add_a_new_provider.views import AssignContractManagerFormView
from app.main.views import ViewProvider
from app.pda.errors import ProviderDataApiError, ProviderDataApiHttpError
from app.views import BaseFormView


class MockFormClass:
    template = "test_form.html"
    title = "Test Form"
    url = "test-form"


class TestBaseFormView:
    def test_init_with_defaults(self):
        view = BaseFormView()
        assert view.form_class == BaseForm
        assert view.template == "form.html"
        assert view.success_endpoint == "main.index"

    def test_init_with_custom_params(self):
        view = BaseFormView(form_class=MockFormClass, template="custom.html", success_endpoint="custom.success")
        assert view.form_class == MockFormClass
        assert view.template == "custom.html"
        assert view.success_endpoint == "custom.success"

    def test_get_form_class(self):
        view = BaseFormView(form_class=MockFormClass)
        assert view.get_form_class() == MockFormClass

    def test_get_template(self):
        view = BaseFormView(template="custom.html")
        assert view.get_template() == "custom.html"

    def test_get_success_url_with_custom_endpoint(self):
        view = BaseFormView(success_endpoint="custom.success")

        with patch("app.views.url_for") as mock_url_for:
            mock_url_for.return_value = "/custom/success"
            result = view.get_success_url()
            mock_url_for.assert_called_once_with("custom.success")
            assert result == "/custom/success"

    def test_get_success_url_with_default(self):
        view = BaseFormView()

        with patch("app.views.url_for") as mock_url_for:
            mock_url_for.return_value = "/main/index"
            result = view.get_success_url()
            mock_url_for.assert_called_once_with("main.index")
            assert result == "/main/index"

    def test_get_context_data_with_title(self):
        view = BaseFormView(form_class=MockFormClass)
        form = Mock()

        context = view.get_context_data(form, context={})

        assert context["form"] == form
        assert context["title"] == "Test Form"

    def test_get_context_data_with_default_title(self):
        class FormWithoutTitle:
            pass

        view = BaseFormView(form_class=FormWithoutTitle)
        form = Mock()

        context = view.get_context_data(form, context={})

        assert context["form"] == form
        assert context["title"] == "Form"

    def test_form_valid(self):
        view = BaseFormView()
        form = Mock()

        with (
            patch("app.views.redirect") as mock_redirect,
            patch.object(view, "get_success_url", return_value="/success"),
        ):
            result = view.form_valid(form)

            view.get_success_url.assert_called_once()
            mock_redirect.assert_called_once_with("/success")
            assert result == mock_redirect.return_value

    def test_form_invalid(self):
        view = BaseFormView()
        form = Mock()
        context = {"form": form, "title": "Test"}

        with (
            patch("app.views.render_template") as mock_render,
            patch.object(view, "get_template", return_value="test.html"),
            patch.object(view, "get_context_data", return_value=context),
        ):
            result = view.form_invalid(form)

            view.get_template.assert_called_once()
            view.get_context_data.assert_called_once_with(form)
            mock_render.assert_called_once_with("test.html", **context)
            assert result == mock_render.return_value

    def test_get_request(self):
        mock_form_class = Mock()
        mock_form = Mock()
        mock_form_class.return_value = mock_form

        view = BaseFormView()
        context = {"form": mock_form, "title": "Test"}

        with (
            patch("app.views.render_template") as mock_render,
            patch.object(view, "get_form_class", return_value=mock_form_class),
            patch.object(view, "get_template", return_value="test.html"),
            patch.object(view, "get_context_data", return_value=context),
        ):
            result = view.get()

            view.get_form_class.assert_called_once()
            mock_form_class.assert_called_once_with()
            view.get_template.assert_called_once()
            view.get_context_data.assert_called_once_with(mock_form)
            mock_render.assert_called_once_with("test.html", **context)
            assert result == mock_render.return_value

    def test_post_request_valid_form(self):
        mock_form_class = Mock()
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = True
        mock_form_class.return_value = mock_form

        view = BaseFormView()

        with (
            patch.object(view, "get_form_class", return_value=mock_form_class),
            patch.object(view, "form_valid", return_value="redirect_response"),
        ):
            result = view.post()

            view.get_form_class.assert_called_once()
            mock_form_class.assert_called_once_with()
            mock_form.validate_on_submit.assert_called_once()
            view.form_valid.assert_called_once_with(mock_form)
            assert result == "redirect_response"

    def test_post_request_invalid_form(self):
        mock_form_class = Mock()
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = False
        mock_form_class.return_value = mock_form

        view = BaseFormView()

        with (
            patch.object(view, "get_form_class", return_value=mock_form_class),
            patch.object(view, "form_invalid", return_value="render_response"),
        ):
            result = view.post()

            view.get_form_class.assert_called_once()
            mock_form_class.assert_called_once_with()
            mock_form.validate_on_submit.assert_called_once()
            view.form_invalid.assert_called_once_with(mock_form)
            assert result == "render_response"


class TestBaseFormViewIntegration:
    def test_view_with_flask_app(self, app):
        with app.app_context():
            view = BaseFormView(form_class=MockFormClass)

            form_class = view.get_form_class()
            assert form_class == MockFormClass

            template = view.get_template()
            assert template == "form.html"

            success_url = view.get_success_url()
            assert success_url == url_for("main.index")

    def test_multiple_view_instances(self):
        view1 = BaseFormView(form_class=MockFormClass, template="form1.html")
        view2 = BaseFormView(template="form2.html", success_endpoint="other.success")

        assert view1.form_class == MockFormClass
        assert view1.template == "form1.html"
        assert view1.success_endpoint == "main.index"

        assert view2.form_class == BaseForm
        assert view2.template == "form2.html"
        assert view2.success_endpoint == "other.success"

    def test_view_inheritance_patterns(self):
        class CustomFormView(BaseFormView):
            form_class = MockFormClass
            template = "custom.html"
            success_endpoint = "custom.success"

        view = CustomFormView()

        assert view.form_class == MockFormClass
        assert view.template == "custom.html"
        assert view.success_endpoint == "custom.success"

        view_with_overrides = CustomFormView(template="override.html", success_endpoint="override.success")

        assert view_with_overrides.form_class == MockFormClass
        assert view_with_overrides.template == "override.html"
        assert view_with_overrides.success_endpoint == "override.success"

    def test_view_methods_called_in_sequence(self):
        view = BaseFormView()
        mock_form = Mock()

        with (
            patch.object(view, "get_form_class") as mock_get_form_class,
            patch.object(view, "get_template") as mock_get_template,
            patch.object(view, "get_context_data") as mock_get_context,
            patch("app.views.render_template") as mock_render,
        ):
            mock_form_class = Mock()
            mock_form_class.return_value = mock_form
            mock_get_form_class.return_value = mock_form_class
            mock_get_template.return_value = "test.html"
            mock_get_context.return_value = {"form": mock_form}

            view.get()

            mock_get_form_class.assert_called_once()
            mock_form_class.assert_called_once()
            mock_get_template.assert_called_once()
            mock_get_context.assert_called_once_with(mock_form)
            mock_render.assert_called_once()

    def test_success_endpoint_flexibility(self):
        view = BaseFormView(success_endpoint="custom.endpoint")

        with patch("app.views.url_for") as mock_url_for:
            mock_url_for.return_value = "/custom/path"
            result = view.get_success_url()

            mock_url_for.assert_called_once_with("custom.endpoint")
            assert result == "/custom/path"


class TestViewProviderRecovery:
    def test_duplicate_provider_conflict_redirects_with_flash(self, app):
        with app.test_request_context("/view-provider"):
            session["new_provider"] = {
                "firm_name": "Duplicate Firm",
                "firm_type": "Legal Services Provider",
            }
            session["new_head_office"] = {"address_line_1": "123 Test Street"}
            session["new_head_office_bank_account"] = {"account_number": "12345678"}
            session["new_liaison_manager"] = {"first_name": "Jane"}

            view = ViewProvider()

            with patch(
                "app.main.views.create_provider_from_session",
                side_effect=ProviderDataApiHttpError(409, "Provider with this name already exists"),
            ):
                response = view.get(None)

            assert response.status_code == 302
            assert response.location == url_for("main.add_parent_provider")
            messages = get_flashed_messages(with_categories=True)
            assert messages == [
                (
                    "error",
                    {
                        "html": "<b>Duplicate Firm already exists.</b> Change the provider name and try again. <a class='govuk-link' href='/add-parent-provider'>Return to Add parent provider</a>.",
                    },
                )
            ]
            assert "new_provider" not in session
            assert "new_head_office" not in session
            assert "new_head_office_bank_account" not in session
            assert "new_liaison_manager" not in session

    def test_non_duplicate_conflict_shows_backend_detail(self, app):
        with app.test_request_context("/view-provider"):
            session["new_provider"] = {
                "firm_name": "Test LSP77",
                "firm_type": "Legal Services Provider",
            }
            session["new_head_office"] = {"address_line_1": "123 Test Street"}

            view = ViewProvider()

            with patch(
                "app.main.views.create_provider_from_session",
                side_effect=ProviderDataApiHttpError(409, "Office account number already exists"),
            ):
                response = view.get(None)

            assert response.status_code == 302
            assert response.location == url_for("main.add_parent_provider")
            messages = get_flashed_messages(with_categories=True)
            assert messages == [
                (
                    "error",
                    {
                        "html": "<b>Unable to create provider due to a data conflict.</b> Office account number already exists Check the details and try again. <a class='govuk-link' href='/add-parent-provider'>Return to Add parent provider</a>.",
                    },
                )
            ]

    def test_non_409_error_shows_backend_detail_and_redirects_to_assign_manager(self, app):
        with app.test_request_context("/view-provider"):
            session["new_provider"] = {
                "firm_name": "Test LSP77",
                "firm_type": "Legal Services Provider",
            }
            session["new_head_office"] = {"address_line_1": "123 Test Street"}

            view = ViewProvider()

            with patch(
                "app.main.views.create_provider_from_session",
                side_effect=ProviderDataApiHttpError(400, "contractManager must be provided"),
            ):
                response = view.get(None)

            assert response.status_code == 302
            assert response.location == url_for("main.assign_contract_manager")
            messages = get_flashed_messages(with_categories=True)
            assert messages == [
                (
                    "error",
                    "Unable to create provider with the configured backend. contractManager must be provided",
                )
            ]


class TestAssignContractManagerRecovery:
    def test_assign_contract_manager_get_shows_user_facing_error_when_load_fails(self, app):
        with app.test_request_context("/assign-contract-manager"):
            session["new_provider"] = {
                "firm_name": "Test LSP",
                "firm_type": "Legal Services Provider",
            }
            session["new_head_office"] = {"address_line_1": "123 Test Street"}

            view = AssignContractManagerFormView(form_class=AssignContractManagerForm)
            app.extensions["pda"].get_list_of_contract_manager_names = Mock(
                side_effect=ProviderDataApiError("Unable to load contract managers with the configured backend")
            )

            with (
                patch("app.main.add_a_new_provider.views.render_template", return_value="rendered"),
            ):
                response = view.get(context={})

            messages = get_flashed_messages(with_categories=True)
            assert ("error", "Unable to load contract managers with the configured backend") in messages
            assert response == "rendered"
