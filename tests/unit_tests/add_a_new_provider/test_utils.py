from unittest.mock import Mock

import pytest
from flask import get_flashed_messages, session
from werkzeug.datastructures import MultiDict

from app.main.add_a_new_provider.forms import AddProviderForm, LiaisonManagerForm
from app.main.utils import add_new_provider, create_provider_from_session
from app.models import Firm
from app.pda.api import ProviderDataApi
from app.pda.errors import ProviderDataApiHttpError
from app.pda.mock_api import MockProviderDataApi


class TestAddNewProvider:
    @pytest.fixture(autouse=True)
    def setup_mock_api(self, app):
        """Ensure each test starts with a clean MockProviderDataApi."""
        with app.app_context():
            # Always ensure we have MockProviderDataApi for these tests
            from app.pda.mock_api import MockProviderDataApi

            mock_pda = MockProviderDataApi()
            mock_pda.init_app(app)
            app.extensions["pda"] = mock_pda

    def test_add_new_provider_success(self, app):
        """Test successfully adding a new provider."""
        with app.app_context():
            # Create a test firm
            firm = Firm(firm_name="TEST FIRM", firm_type="Legal Services Provider", constitutional_status="Partnership")

            # Call add_new_provider
            result = add_new_provider(firm)

            # Verify the result
            assert isinstance(result, Firm)
            assert result.firm_name == "TEST FIRM"
            assert result.firm_type == "Legal Services Provider"
            assert result.firm_id is not None
            assert result.firm_id > 0

    def test_add_new_provider_pda_not_initialized(self, app):
        """Test error when PDA is not initialized."""
        with app.app_context():
            # Remove PDA from extensions
            if "pda" in app.extensions:
                del app.extensions["pda"]

            firm = Firm(firm_name="TEST FIRM", firm_type="Legal Services Provider")

            with pytest.raises(RuntimeError, match="Provider Data API not initialized"):
                add_new_provider(firm)

    def test_add_new_provider_non_mock_adapter(self, app):
        """Test add_new_provider delegates to a non-mock PDA adapter."""
        with app.app_context():
            real_pda = ProviderDataApi()
            real_pda.create_provider_firm = Mock(
                return_value=Firm(
                    firmName="TEST FIRM",
                    firmType="Legal Services Provider",
                    constitutionalStatus="Partnership",
                    firmId=123,
                    firmNumber="123",
                )
            )
            app.extensions["pda"] = real_pda

            firm = Firm(firm_name="TEST FIRM", firm_type="Legal Services Provider")

            result = add_new_provider(firm)

            real_pda.create_provider_firm.assert_called_once_with(
                firm,
                office=None,
                liaison_manager=None,
                bank_account=None,
                contract_manager_guid=None,
            )
            assert result.firm_id == 123

    def test_add_new_provider_preserves_firm_data(self, app):
        """Test that all firm data is preserved during creation."""
        with app.app_context():
            # Verify we're using MockProviderDataApi
            pda = app.extensions.get("pda")
            assert isinstance(pda, MockProviderDataApi), f"Expected MockProviderDataApi, got {type(pda)}"

            firm = Firm(
                firm_name="COMPREHENSIVE TEST FIRM",
                firm_type="Chambers",
                constitutional_status="Limited Company",
                website_url="https://example.com",
                small_business_flag="Y",
                women_owned_flag="Y",
            )

            result = add_new_provider(firm)

            # Verify all fields are preserved
            assert result.firm_name == "COMPREHENSIVE TEST FIRM"
            assert result.firm_type == "Chambers"
            assert result.constitutional_status == "Limited Company"
            assert result.website_url == "https://example.com"
            assert result.small_business_flag == "Y"
            assert result.women_owned_flag == "Y"
            # New fields should be assigned
            assert result.firm_id is not None
            assert result.firm_number is not None
            assert result.ccms_firm_id is not None

    def test_add_new_provider_shows_success_flash(self, app):
        """Test that success flash message is shown when provider is created."""
        with app.app_context():
            firm = Firm(
                firm_name="TEST FLASH FIRM", firm_type="Legal Services Provider", constitutional_status="Partnership"
            )

            # Call add_new_provider
            add_new_provider(firm)

            # Verify flash message was added
            messages = get_flashed_messages(with_categories=True)
            assert len(messages) == 1
            category, message = messages[0]
            assert category == "success"
            assert message == "<b>New legal services provider successfully created</b>"

    def test_add_new_provider_liaison_manager_email_with_spaces(self, app):
        form = LiaisonManagerForm(formdata=MultiDict({"email_address": " test@local.com "}))
        form.validate()
        assert "email_address" not in form.errors

    def test_add_provider_form_duplicate_name_validation(self, app):
        with app.test_request_context():
            pda = app.extensions["pda"]
            pda.provider_name_exists = Mock(return_value=True)

            form = AddProviderForm(
                meta={"csrf": False},
                formdata=MultiDict({"provider_name": "Duplicate Firm", "provider_type": "Legal Services Provider"}),
            )

            assert form.validate() is False
            assert form.provider_name.errors == ["A provider named Duplicate Firm already exists"]


class TestCreateProviderFromSession:
    @pytest.fixture(autouse=True)
    def setup_mock_api(self, app):
        """Ensure each test starts with a clean MockProviderDataApi."""
        with app.app_context():
            from app.pda.mock_api import MockProviderDataApi

            mock_pda = MockProviderDataApi()
            mock_pda.init_app(app)
            app.extensions["pda"] = mock_pda

    def test_create_provider_from_session_no_session_data(self, app):
        """Test that function returns None when no session data exists."""
        with app.test_request_context():
            result = create_provider_from_session()
            assert result is None

    def test_create_provider_from_session_firm_only(self, app):
        """Test creating provider with only firm data in session."""
        with app.test_request_context():
            # Set up firm session data
            session["new_provider"] = {
                "firm_name": "Test Session Firm",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Limited Company",
            }

            result = create_provider_from_session()

            # Verify firm was created
            assert result is not None
            assert isinstance(result, Firm)
            assert result.firm_name == "Test Session Firm"
            assert result.firm_type == "Legal Services Provider"
            assert result.firm_id is not None

            # Verify session was cleaned up
            assert "new_provider" not in session

    def test_create_provider_from_session_non_mock_uses_nested_provider_create(self, app):
        with app.test_request_context():
            real_pda = ProviderDataApi()
            real_pda.create_provider_firm = Mock(
                return_value=Firm(
                    firmName="Nested Test Firm",
                    firmType="Legal Services Provider",
                    constitutionalStatus="Limited Company",
                    firmId=999,
                    firmNumber="999",
                )
            )
            app.extensions["pda"] = real_pda

            session["new_provider"] = {
                "firm_name": "Nested Test Firm",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Limited Company",
            }
            session["new_head_office"] = {
                "address_line_1": "123 Test Street",
                "city": "Test City",
                "postcode": "TE1 5ST",
                "telephone_number": "01234567890",
                "email_address": "test@example.com",
                "payment_method": "Cheque",
                "contract_manager_guid": "cm-guid-001",
            }
            session["new_liaison_manager"] = {
                "first_name": "Test",
                "last_name": "User",
                "email_address": "test.user@example.com",
                "telephone_number": "01234567890",
                "job_title": "Liaison manager",
                "primary": "Y",
            }

            result = create_provider_from_session()

            assert result.firm_id == 999
            real_pda.create_provider_firm.assert_called_once()
            _, kwargs = real_pda.create_provider_firm.call_args
            assert kwargs["office"].address_line_1 == "123 Test Street"
            assert kwargs["liaison_manager"].first_name == "Test"
            assert kwargs["contract_manager_guid"] == "cm-guid-001"
            assert "new_provider" not in session
            assert "new_head_office" not in session
            assert "new_liaison_manager" not in session

    def test_create_provider_from_session_non_mock_failure_preserves_session(self, app):
        with app.test_request_context():
            real_pda = ProviderDataApi()
            real_pda.create_provider_firm = Mock(side_effect=ProviderDataApiHttpError(409, "Conflict"))
            app.extensions["pda"] = real_pda

            session["new_provider"] = {
                "firm_name": "Duplicate Firm",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Limited Company",
            }
            session["new_head_office"] = {
                "address_line_1": "123 Test Street",
                "city": "Test City",
                "postcode": "TE1 5ST",
                "payment_method": "Cheque",
                "contract_manager_guid": "cm-guid-001",
            }
            session["new_liaison_manager"] = {
                "first_name": "Test",
                "last_name": "User",
                "email_address": "test.user@example.com",
                "telephone_number": "01234567890",
                "job_title": "Liaison manager",
                "primary": "Y",
            }

            with pytest.raises(ProviderDataApiHttpError):
                create_provider_from_session()

            assert session["new_provider"]["firm_name"] == "Duplicate Firm"
            assert session["new_head_office"]["address_line_1"] == "123 Test Street"
            assert session["new_liaison_manager"]["first_name"] == "Test"

    def test_create_provider_from_session_with_office(self, app):
        """Test creating provider with firm and office data in session."""
        with app.test_request_context():
            # Set up session data
            session["new_provider"] = {
                "firm_name": "Test Firm With Office",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Partnership",
            }
            session["new_head_office"] = {
                "address_line_1": "123 Test Street",
                "city": "Test City",
                "postcode": "TE1 5ST",
                "telephone_number": "01234567890",
                "email_address": "test@example.com",
                "payment_method": "Electronic",
            }

            result = create_provider_from_session()

            # Verify firm was created
            assert result is not None
            assert result.firm_name == "Test Firm With Office"

            # Verify office was created
            pda = app.extensions["pda"]
            offices = pda.get_provider_offices(result.firm_id)
            assert len(offices) == 1
            office = offices[0]
            assert office.address_line_1 == "123 Test Street"
            assert office.city == "Test City"
            assert office.postcode == "TE1 5ST"
            assert office.payment_method == "Electronic"

            # Verify sessions were cleaned up
            assert "new_provider" not in session
            assert "new_head_office" not in session

    def test_create_provider_from_session_with_bank_account(self, app):
        """Test creating provider with firm, office, and bank account data."""
        with app.test_request_context():
            # Set up session data
            session["new_provider"] = {
                "firm_name": "Test Firm With Bank",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Limited Company",
            }
            session["new_head_office"] = {
                "address_line_1": "456 Banking Street",
                "city": "Finance City",
                "postcode": "FC2 1BA",
                "telephone_number": "09876543210",
                "email_address": "finance@example.com",
                "payment_method": "Electronic",
            }
            session["new_head_office_bank_account"] = {
                "bank_account_name": "Test Business Account",
                "sort_code": "123456",
                "account_number": "87654321",
            }

            result = create_provider_from_session()

            # Verify firm was created
            assert result is not None
            assert result.firm_name == "Test Firm With Bank"

            # Verify office was created
            pda = app.extensions["pda"]
            offices = pda.get_provider_offices(result.firm_id)
            assert len(offices) == 1
            office = offices[0]
            assert office.address_line_1 == "456 Banking Street"
            assert office.payment_method == "Electronic"

            # Verify bank account was created
            bank_accounts = pda.get_office_bank_accounts(result.firm_id, office.firm_office_code)
            assert len(bank_accounts) == 1
            bank_account = bank_accounts[0]
            assert bank_account.bank_account_name == "Test Business Account"
            assert bank_account.sort_code == "123456"
            assert bank_account.account_number == "87654321"

            # Verify sessions were cleaned up
            assert "new_provider" not in session
            assert "new_head_office" not in session
            assert "new_head_office_bank_account" not in session

    def test_create_provider_from_session_partial_bank_data(self, app):
        """Test that bank account is created with partial data (only required fields)."""
        with app.test_request_context():
            # Set up session data with only required bank account fields
            session["new_provider"] = {
                "firm_name": "Test Partial Bank Firm",
                "firm_type": "Chambers",
                "constitutional_status": "Partnership",
            }
            session["new_head_office"] = {
                "address_line_1": "789 Partial Street",
                "city": "Incomplete City",
                "postcode": "IC3 2PA",
                "telephone_number": "01111111111",
                "email_address": "partial@example.com",
            }
            session["new_head_office_bank_account"] = {
                # Only required bank account data
                "bank_account_name": "Partial Account",
                "sort_code": "123456",
                "account_number": "87654321",
                # Missing optional fields like bank_name, bank_branch_name, etc.
            }

            result = create_provider_from_session()

            # Verify firm was created
            assert result is not None
            assert result.firm_name == "Test Partial Bank Firm"

            # Verify office was created
            pda = app.extensions["pda"]
            offices = pda.get_provider_offices(result.firm_id)
            assert len(offices) == 1
            office = offices[0]
            assert office.address_line_1 == "789 Partial Street"

            # Verify bank account was created with required fields only
            bank_accounts = pda.get_office_bank_accounts(result.firm_id, office.firm_office_code)
            assert len(bank_accounts) == 1
            bank_account = bank_accounts[0]
            assert bank_account.bank_account_name == "Partial Account"
            assert bank_account.sort_code == "123456"
            assert bank_account.account_number == "87654321"
            # Optional fields should be None or defaults
            assert bank_account.bank_name is None
            assert bank_account.bank_branch_name is None

    def test_create_provider_from_session_no_bank_account_when_skipped(self, app):
        """Test that no bank account is created when user skipped the bank account step."""
        with app.test_request_context():
            # Set up session data without bank account session key (simulating skip)
            session["new_provider"] = {
                "firm_name": "Test Skip Bank Firm",
                "firm_type": "Legal Services Provider",
                "constitutional_status": "Partnership",
            }
            session["new_head_office"] = {
                "address_line_1": "789 Skip Street",
                "city": "Skip City",
                "postcode": "SK1 5IP",
                "telephone_number": "09876543210",
                "email_address": "skip@example.com",
            }
            # No new_head_office_bank_account session key (simulating skip)

            result = create_provider_from_session()

            # Verify firm was created
            assert result is not None
            assert result.firm_name == "Test Skip Bank Firm"

            # Verify office was created
            pda = app.extensions["pda"]
            offices = pda.get_provider_offices(result.firm_id)
            assert len(offices) == 1
            office = offices[0]
            assert office.address_line_1 == "789 Skip Street"

            # Verify no bank account was created (since skip was used)
            bank_accounts = pda.get_office_bank_accounts(result.firm_id, office.firm_office_code)
            assert bank_accounts == []
