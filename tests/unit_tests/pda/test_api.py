from unittest.mock import Mock

import pytest
import requests

from app.models import Contact, Firm, Office
from app.pda.api import PDAConnectionError, PDAError, ProviderDataApi


class TestProviderDataApi:
    @pytest.fixture
    def api_client(self):
        return ProviderDataApi()

    @pytest.fixture
    def mock_app(self):
        app = Mock()
        app.extensions = {}
        return app

    @pytest.fixture
    def initialized_client(self, api_client, mock_app):
        api_client.init_app(mock_app, base_url="https://mock.provider-data-api.com", api_key="test-key")
        return api_client

    def test_init_app_success(self, api_client, mock_app):
        api_client.init_app(mock_app, base_url="https://mock.provider-data-api.com", api_key="test-key")

        assert api_client.base_url == "https://mock.provider-data-api.com"
        assert api_client._initialized
        assert mock_app.extensions["pda"] == api_client
        assert api_client.session.headers["X-Authorization"] == "test-key"

    def test_init_app_missing_base_url(self, api_client, mock_app):
        with pytest.raises(ValueError, match="Must provide a base URL"):
            api_client.init_app(mock_app, base_url=None, api_key="test-key")

    def test_init_app_missing_api_key(self, api_client, mock_app):
        with pytest.raises(ValueError, match="Must provide an API key"):
            api_client.init_app(mock_app, base_url="https://mock.provider-data-api.com", api_key=None)

    def test_test_connection_success(self, initialized_client):
        mock_response = Mock()
        mock_response.status_code = 200
        initialized_client.session.request = Mock(return_value=mock_response)

        result = initialized_client.test_connection()

        assert result is True

    def test_test_connection_failure(self, initialized_client):
        initialized_client.session.request = Mock(side_effect=requests.RequestException("Connection failed"))

        with pytest.raises(PDAConnectionError):
            initialized_client.test_connection()

    def test_test_connection_not_initialized(self, api_client):
        with pytest.raises(PDAError, match="API client not initialized"):
            api_client.test_connection()

    def test_make_request_success(self, initialized_client):
        mock_response = Mock()
        initialized_client.session.request = Mock(return_value=mock_response)

        result = initialized_client._make_request("GET", "/test")

        assert result == mock_response

    def test_make_request_failure(self, initialized_client):
        initialized_client.session.request = Mock(side_effect=requests.RequestException("Request failed"))

        with pytest.raises(PDAError):
            initialized_client._make_request("GET", "/test")

    def test_handle_response_200(self, initialized_client):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}

        result = initialized_client._handle_response(mock_response, {})

        assert result == {"key": "value"}

    def test_handle_response_204(self, initialized_client):
        mock_response = Mock()
        mock_response.status_code = 204

        result = initialized_client._handle_response(mock_response, [])

        assert result == []

    def test_handle_response_404(self, initialized_client):
        mock_response = Mock()
        mock_response.status_code = 404

        result = initialized_client._handle_response(mock_response, None)

        assert result is None

    def test_handle_response_http_error(self, initialized_client):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")

        with pytest.raises(PDAError):
            initialized_client._handle_response(mock_response, {})

    def test_get_provider_firm_success(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        mock_firm = {
            "firmId": 123,
            "constitutionalStatus": "Charity",
        }
        initialized_client._handle_response = Mock(return_value={"firm": mock_firm})

        result = initialized_client.get_provider_firm(123)

        initialized_client.get.assert_called_once_with("/provider-firms/123")
        assert result == Firm(**mock_firm)

    def test_get_provider_firm_with_data_envelope(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        mock_firm = {
            "firmId": 123,
            "constitutionalStatus": "Charity",
        }
        initialized_client._handle_response = Mock(return_value={"data": {"firm": mock_firm}})

        result = initialized_client.get_provider_firm(123)

        initialized_client.get.assert_called_once_with("/provider-firms/123")
        assert result == Firm(**mock_firm)

    def test_get_provider_firm_invalid_id(self, initialized_client):
        with pytest.raises(ValueError, match="firm_id must be a positive integer"):
            initialized_client.get_provider_firm(-1)

    def test_get_all_provider_firms(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        mock_firm = {
            "firmId": 123,
            "constitutionalStatus": "Charity",
        }
        initialized_client._handle_response = Mock(return_value={"firms": [mock_firm]})

        result = initialized_client.get_all_provider_firms()

        initialized_client.get.assert_called_once_with("/provider-firms")
        assert result == [Firm(**mock_firm)]

    def test_get_all_provider_firms_with_data_content_envelope(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        mock_firm = {
            "firmId": 123,
            "constitutionalStatus": "Charity",
        }
        initialized_client._handle_response = Mock(return_value={"data": {"content": [mock_firm]}})

        result = initialized_client.get_all_provider_firms()

        initialized_client.get.assert_called_once_with("/provider-firms")
        assert result == [Firm(**mock_firm)]

    def test_get_provider_office_success(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"firm_office_code": "1A234B"})

        result = initialized_client.get_provider_office("1A234B")

        initialized_client.get.assert_called_once_with("/provider-offices/1A234B")
        assert result == Office(firm_office_code="1A234B")

    def test_get_provider_office_falls_back_to_provider_firms_offices(self, initialized_client):
        initialized_client.get = Mock(side_effect=[Mock(status_code=404), Mock(status_code=200)])
        initialized_client._handle_response = Mock(
            side_effect=[None, {"data": {"content": [{"firm_office_code": "1A234B"}]}}]
        )

        result = initialized_client.get_provider_office("1A234B")

        assert initialized_client.get.call_count == 2
        initialized_client.get.assert_any_call("/provider-offices/1A234B")
        initialized_client.get.assert_any_call(
            "/provider-firms-offices", params={"officeCode": "1A234B", "pageSize": 1}
        )
        assert result == Office(firm_office_code="1A234B")

    def test_get_provider_office_invalid_code(self, initialized_client):
        with pytest.raises(ValueError, match="office_code must be a non-empty string"):
            initialized_client.get_provider_office("")

    def test_get_provider_offices(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"offices": [{"firm_office_code": "1A234B"}]})

        result = initialized_client.get_provider_offices(123)

        initialized_client.get.assert_called_once_with("/provider-firms/123/provider-offices")
        assert result == [Office(firm_office_code="1A234B")]

    def test_get_provider_offices_falls_back_to_new_offices_endpoint(self, initialized_client):
        initialized_client.get = Mock(side_effect=[Mock(status_code=404), Mock(status_code=200)])
        initialized_client._handle_response = Mock(
            side_effect=[[], {"data": {"content": [{"firm_office_code": "1A234B"}]}}]
        )

        result = initialized_client.get_provider_offices(123)

        assert initialized_client.get.call_count == 2
        initialized_client.get.assert_any_call("/provider-firms/123/provider-offices")
        initialized_client.get.assert_any_call("/provider-firms/123/offices")
        assert result == [Office(firm_office_code="1A234B")]

    def test_get_provider_users(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value=[{"user_id": 1}])

        result = initialized_client.get_provider_users(123)

        initialized_client.get.assert_called_once_with("/provider-firms/123/provider-users")
        assert result == [{"user_id": 1}]

    def test_get_office_contract_details(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"contract_id": "1A234B"})

        result = initialized_client.get_office_contract_details(123, "1A234B")

        initialized_client.get.assert_called_once_with(
            "/provider-firms/123/provider-offices/1A234B/office-contract-details"
        )
        assert result == {"contract_id": "1A234B"}

    def test_get_office_schedule_details(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"scheduleId": "456"})

        result = initialized_client.get_office_schedule_details(123, "1A234B")

        initialized_client.get.assert_called_once_with("/provider-firms/123/provider-offices/1A234B/schedules")
        assert result == {"scheduleId": "456"}

    def test_get_office_bank_details(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value=[{"accountNumber": "12345678"}])

        banks_accounts = initialized_client.get_office_bank_accounts(123, "1A234B")

        initialized_client.get.assert_called_once_with(
            "/provider-firms/123/provider-offices/1A234B/bank-account-details"
        )
        assert len(banks_accounts) == 1
        assert banks_accounts[0].account_number == "12345678"

    def test_get_office_bank_details_falls_back_to_bank_details_endpoint(self, initialized_client):
        initialized_client.get = Mock(side_effect=[Mock(status_code=404), Mock(status_code=200)])
        initialized_client._handle_response = Mock(
            side_effect=[[], {"data": {"content": [{"accountNumber": "12345678"}]}}]
        )

        bank_accounts = initialized_client.get_office_bank_accounts(123, "1A234B")

        assert initialized_client.get.call_count == 2
        initialized_client.get.assert_any_call("/provider-firms/123/provider-offices/1A234B/bank-account-details")
        initialized_client.get.assert_any_call("/provider-firms/123/offices/1A234B/bank-details")
        assert len(bank_accounts) == 1
        assert bank_accounts[0].account_number == "12345678"

    def test_get_office_bank_details_normalizes_pda_r2_shape(self, initialized_client):
        initialized_client.get = Mock(side_effect=[Mock(status_code=404), Mock(status_code=200)])
        initialized_client._handle_response = Mock(
            side_effect=[
                [],
                {
                    "data": {
                        "content": [
                            {
                                "guid": "abc-123",
                                "accountName": "Test Child Office Account",
                                "sortCode": "300000",
                                "accountNumber": "00000001",
                                "activeDateFrom": "2026-08-04",
                                "primaryFlag": True,
                            }
                        ]
                    }
                },
            ]
        )

        bank_accounts = initialized_client.get_office_bank_accounts(123, "ACC006")

        assert len(bank_accounts) == 1
        assert bank_accounts[0].bank_account_name == "Test Child Office Account"
        assert bank_accounts[0].sort_code == "300000"
        assert bank_accounts[0].account_number == "00000001"
        assert bank_accounts[0].primary_flag == "Y"

    def test_update_office_payment_method(self, initialized_client):
        initialized_client.patch_office = Mock(return_value={})
        initialized_client.get_provider_office = Mock(return_value=Office(firm_office_code="1A234B"))

        result = initialized_client.update_office_payment_method(123, "1A234B", "Electronic")

        initialized_client.patch_office.assert_called_once_with(123, "1A234B", {"paymentMethod": "EFT"})
        assert result == Office(firm_office_code="1A234B")

    def test_patch_provider_firm(self, initialized_client):
        initialized_client.patch_provider = Mock(return_value=Firm(firmId=123, constitutionalStatus="Charity"))

        result = initialized_client.patch_provider_firm(123, {"inactiveDate": None})

        initialized_client.patch_provider.assert_called_once_with(123, {"inactiveDate": None})
        assert result == Firm(firmId=123, constitutionalStatus="Charity")

    def test_update_provider_firm_name(self, initialized_client):
        initialized_client.patch_provider = Mock(return_value=Firm(firmId=123, constitutionalStatus="Charity"))

        result = initialized_client.update_provider_firm_name(123, "New Name")

        initialized_client.patch_provider.assert_called_once_with(123, {"firmName": "New Name"})
        assert result == Firm(firmId=123, constitutionalStatus="Charity")

    def test_update_lsp_details(self, initialized_client):
        initialized_client.patch_provider = Mock(return_value=Firm(firmId=123, constitutionalStatus="Charity"))

        result = initialized_client.update_legal_service_provider_details(123, {"constitutionalStatus": "Charity"})

        initialized_client.patch_provider.assert_called_once_with(123, {"constitutionalStatus": "Charity"})
        assert result == Firm(firmId=123, constitutionalStatus="Charity")

    def test_update_barrister_details(self, initialized_client):
        initialized_client.patch_provider = Mock(return_value=Firm(firmId=123, constitutionalStatus="Charity"))

        result = initialized_client.update_barrister_details(123, {"firmName": "Barrister One"})

        initialized_client.patch_provider.assert_called_once_with(123, {"firmName": "Barrister One"})
        assert result == Firm(firmId=123, constitutionalStatus="Charity")

    def test_update_advocate_details(self, initialized_client):
        initialized_client.patch_provider = Mock(return_value=Firm(firmId=123, constitutionalStatus="Charity"))

        result = initialized_client.update_advocate_details(123, {"firmName": "Advocate One"})

        initialized_client.patch_provider.assert_called_once_with(123, {"firmName": "Advocate One"})
        assert result == Firm(firmId=123, constitutionalStatus="Charity")

    def test_update_office_false_balance(self, initialized_client):
        initialized_client.patch_office = Mock(return_value={})
        initialized_client.get_provider_office = Mock(return_value=Office(firm_office_code="1A234B"))

        result = initialized_client.update_office_false_balance(123, "1A234B", {"contractManager": "X"})

        initialized_client.patch_office.assert_called_once_with(123, "1A234B", {"contractManager": "X"})
        assert result == Office(firm_office_code="1A234B")

    def test_update_office_intervened_date(self, initialized_client):
        initialized_client.patch_office = Mock(return_value={})
        initialized_client.get_provider_office = Mock(return_value=Office(firm_office_code="1A234B"))

        result = initialized_client.update_office_intervened_date(123, "1A234B", {"intervenedDate": "2026-08-04"})

        initialized_client.patch_office.assert_called_once_with(
            123,
            "1A234B",
            {
                "intervenedDate": "2026-08-04",
                "intervenedFlag": True,
                "intervenedChangeDate": "2026-08-04",
            },
        )
        assert result == Office(firm_office_code="1A234B")

    def test_update_office_debt_recovery(self, initialized_client):
        initialized_client.patch_office = Mock(return_value={})
        initialized_client.get_provider_office = Mock(return_value=Office(firm_office_code="1A234B"))

        result = initialized_client.update_office_debt_recovery(123, "1A234B", {"debtRecoveryFlag": "Yes"})

        initialized_client.patch_office.assert_called_once_with(123, "1A234B", {"debtRecoveryFlag": True})
        assert result == Office(firm_office_code="1A234B")

    def test_update_office_hold_payments(self, initialized_client):
        initialized_client.patch_office = Mock(return_value={})
        initialized_client.get_provider_office = Mock(return_value=Office(firm_office_code="1A234B"))

        result = initialized_client.update_office_hold_payments(123, "1A234B", {"holdAllPaymentsFlag": "N"})

        initialized_client.patch_office.assert_called_once_with(123, "1A234B", {"holdAllPaymentsFlag": False})
        assert result == Office(firm_office_code="1A234B")

    def test_get_office_contacts_from_liaison_managers(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(
            return_value={
                "data": {
                    "content": [
                        {
                            "firstName": "Alice",
                            "lastName": "Johnson",
                            "emailAddress": "alice@test.example.com",
                            "telephoneNumber": "012345",
                            "activeDateFrom": "2026-08-04",
                            "linkedFlag": True,
                        }
                    ]
                }
            }
        )
        initialized_client.get_provider_office = Mock(return_value=Office(firmOfficeId=3, firmOfficeCode="ACC003"))

        result = initialized_client.get_office_contacts(100003, "ACC003")

        initialized_client.get.assert_called_once_with("/provider-firms/100003/offices/ACC003/liaison-managers")
        assert result == [
            Contact(
                vendorSiteId=3,
                firstName="Alice",
                lastName="Johnson",
                emailAddress="alice@test.example.com",
                telephoneNumber="012345",
                website=None,
                jobTitle="Liaison manager",
                primary="Y",
                activeFrom="2026-08-04",
            )
        ]
