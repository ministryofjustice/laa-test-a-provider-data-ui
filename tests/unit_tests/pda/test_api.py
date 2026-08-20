from unittest.mock import Mock

import pytest
import requests

from app.models import Contact, Firm, Office
from app.pda.api import PDAConnectionError, PDAError, ProviderDataApi
from app.pda.errors import ProviderDataApiHttpError


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

    def test_post(self, initialized_client):
        mock_response = Mock()
        initialized_client.session.request = Mock(return_value=mock_response)

        result = initialized_client.post("/test", json={"name": "Firm"})

        assert result == mock_response

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

        with pytest.raises(ProviderDataApiHttpError):
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

    def test_get_provider_firm_maps_companies_house_alias(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(
            return_value={
                "data": {
                    "firm": {
                        "firmId": 123,
                        "firmName": "Test LSP",
                        "firmType": "Legal Services Provider",
                        "constitutionalStatus": "Limited Company",
                        "companiesHouseNumber": "CH-12345",
                        "indemnityReceivedDate": "2026-08-10",
                    }
                }
            }
        )

        result = initialized_client.get_provider_firm(123)

        assert result.company_house_number == "CH-12345"
        assert result.constitutional_status == "Limited Company"
        assert result.indemnity_received_date == "2026-08-10"

    def test_get_provider_firm_invalid_id(self, initialized_client):
        with pytest.raises(ValueError, match="firm_id must be a positive integer or non-empty string"):
            initialized_client.get_provider_firm(-1)

    def test_get_provider_firm_accepts_string_identifier(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        mock_firm = {
            "firmId": 123,
            "constitutionalStatus": "Charity",
        }
        initialized_client._handle_response = Mock(return_value={"firm": mock_firm})

        result = initialized_client.get_provider_firm("3856")

        initialized_client.get.assert_called_once_with("/provider-firms/3856")
        assert result == Firm(**mock_firm)

    def test_create_provider_firm_posts_then_hydrates_by_identifier(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"data": {"providerFirmNumber": "3856"}})
        initialized_client.get_provider_firm = Mock(
            return_value=Firm(
                firmId=3856,
                firmNumber="3856",
                firmName="TEST FIRM",
                firmType="Legal Services Provider",
                constitutionalStatus="Partnership",
            )
        )
        firm = Firm(firmName="TEST FIRM", firmType="Legal Services Provider", constitutionalStatus="Partnership")

        result = initialized_client.create_provider_firm(firm)

        initialized_client.post.assert_called_once_with(
            "/provider-firms",
            json={
                "name": "TEST FIRM",
                "firmType": "Legal Services Provider",
                "legalServicesProvider": {"constitutionalStatus": "Partnership"},
            },
        )
        initialized_client.get_provider_firm.assert_called_once_with("3856")
        assert result.firm_number == "3856"

    def test_create_provider_firm_requires_identifier_in_response(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"data": {}})
        firm = Firm(firmName="TEST FIRM", firmType="Legal Services Provider", constitutionalStatus="Partnership")

        with pytest.raises(PDAError, match="Create provider response did not include a provider identifier"):
            initialized_client.create_provider_firm(firm)

    def test_create_provider_firm_posts_full_nested_lsp_payload(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client.patch = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"data": {"providerFirmNumber": "3856"}})
        initialized_client.get_provider_firm = Mock(
            return_value=Firm(
                firmId=3856,
                firmNumber="3856",
                firmName="TEST FIRM",
                firmType="Legal Services Provider",
                constitutionalStatus="Limited Company",
            )
        )
        firm = Firm(firmName="TEST FIRM", firmType="Legal Services Provider", constitutionalStatus="Limited Company")
        office = Office(
            addressLine1="45 Kings Ride",
            addressLine2="Penn",
            addressLine4="45 Kings Ride",
            city="High Wycombe",
            county="Buckinghamshire",
            postCode="HP108BP",
            telephoneNumber="07438342964",
            emailAddress="smanikyam@gmail.com",
            dxNumber="DX00001",
            dxCentre="Leeds DX Centre",
            paymentMethod="Cheque",
        )
        liaison_manager = Contact(
            vendorSiteId=1,
            firstName="Solomon Philip",
            lastName="Manikyam",
            emailAddress="smanikyam@gmail.com",
            telephoneNumber="07438342964",
        )

        initialized_client.create_provider_firm(
            firm,
            office=office,
            liaison_manager=liaison_manager,
            contract_manager_guid="cm-guid-001",
        )

        initialized_client.post.assert_called_once_with(
            "/provider-firms",
            json={
                "name": "TEST FIRM",
                "firmType": "Legal Services Provider",
                "legalServicesProvider": {
                    "constitutionalStatus": "Limited Company",
                    "address": {
                        "line1": "45 Kings Ride",
                        "line2": "Penn",
                        "line4": "45 Kings Ride",
                        "townOrCity": "High Wycombe",
                        "county": "Buckinghamshire",
                        "postcode": "HP108BP",
                    },
                    "payment": {"paymentMethod": "CHECK"},
                    "liaisonManager": {
                        "firstName": "Solomon Philip",
                        "lastName": "Manikyam",
                        "emailAddress": "smanikyam@gmail.com",
                        "telephoneNumber": "07438342964",
                    },
                    "contractManager": {"contractManagerGUID": "cm-guid-001"},
                    "telephoneNumber": "07438342964",
                    "emailAddress": "smanikyam@gmail.com",
                    "dxDetails": {"dxNumber": "DX00001", "dxCentre": "Leeds DX Centre"},
                },
            },
        )
        initialized_client.patch.assert_called_once_with(
            "/provider-firms/3856",
            json={
                "legalServicesProvider": {
                    "constitutionalStatus": "Limited Company",
                }
            },
        )

    def test_create_provider_firm_patches_lsp_optional_fields_after_create(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client.patch = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(return_value={"data": {"providerFirmNumber": "3856"}})
        initialized_client.get_provider_firm = Mock(
            return_value=Firm(
                firmId=3856,
                firmNumber="3856",
                firmName="TEST FIRM",
                firmType="Legal Services Provider",
                constitutionalStatus="Limited Company",
            )
        )
        firm = Firm(
            firmName="TEST FIRM",
            firmType="Legal Services Provider",
            constitutionalStatus="Limited Company",
            indemnityReceivedDate="2026-08-10",
            companyHouseNumber="CH123456",
        )
        office = Office(addressLine1="1 Test Way", city="Leeds", postCode="LS1 1AA", paymentMethod="Cheque")
        liaison_manager = Contact(
            vendorSiteId=1,
            firstName="Temp",
            lastName="Office",
            emailAddress="temp.office@example.com",
            telephoneNumber="01134960000",
        )

        initialized_client.create_provider_firm(firm, office=office, liaison_manager=liaison_manager)

        initialized_client.patch.assert_called_once_with(
            "/provider-firms/3856",
            json={
                "legalServicesProvider": {
                    "constitutionalStatus": "Limited Company",
                    "indemnityReceivedDate": "2026-08-10",
                    "companiesHouseNumber": "CH123456",
                }
            },
        )

    def test_create_provider_firm_does_not_fail_when_post_create_lsp_patch_conflicts(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client.patch = Mock(return_value=Mock(status_code=409))
        initialized_client.get_provider_firm = Mock(
            return_value=Firm(
                firmId=3856,
                firmNumber="3856",
                firmName="TEST FIRM",
                firmType="Legal Services Provider",
                constitutionalStatus="Limited Company",
            )
        )

        patch_error_response = Mock()
        patch_error_response.status_code = 409
        patch_error_response.url = "https://mock.provider-data-api.com/provider-firms/3856"
        patch_error_response.json.return_value = {"detail": "Version conflict"}
        patch_error_response.raise_for_status.side_effect = requests.HTTPError("Conflict")

        initialized_client._handle_response = Mock(
            side_effect=[
                {"data": {"providerFirmNumber": "3856"}},
                ProviderDataApiHttpError(409, "Version conflict", {"detail": "Version conflict"}),
            ]
        )

        firm = Firm(
            firmName="TEST FIRM",
            firmType="Legal Services Provider",
            constitutionalStatus="Limited Company",
            companyHouseNumber="CH123456",
        )
        office = Office(addressLine1="1 Test Way", city="Leeds", postCode="LS1 1AA", paymentMethod="Cheque")
        liaison_manager = Contact(
            vendorSiteId=1,
            firstName="Temp",
            lastName="Office",
            emailAddress="temp.office@example.com",
            telephoneNumber="01134960000",
        )

        result = initialized_client.create_provider_firm(firm, office=office, liaison_manager=liaison_manager)

        assert result.firm_number == "3856"
        initialized_client.get_provider_firm.assert_called_once_with("3856")

    def test_create_provider_firm_posts_practitioner_payload_with_mandatory_fields(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client._handle_response = Mock(return_value={"data": {"providerFirmNumber": "4001"}})
        initialized_client.get_provider_firm = Mock(
            return_value=Firm(
                firmId=4001,
                firmNumber="4001",
                firmName="TEST ADVOCATE",
                firmType="Advocate",
                constitutionalStatus="N/A",
            )
        )
        firm = Firm(
            firmName="TEST ADVOCATE",
            firmType="Advocate",
            solicitorAdvocateYN="Yes",
            advocateLevel="Junior",
            barCouncilRoll="SRA1234",
            parentFirmId=12345,
        )

        initialized_client.create_provider_firm(firm)

        initialized_client.post.assert_called_once_with(
            "/provider-firms",
            json={
                "name": "TEST ADVOCATE",
                "firmType": "Advocate",
                "practitioner": {
                    "advocateType": "Advocate",
                    "parentFirms": [{"parentFirmNumber": "12345"}],
                    "liaisonManager": {"useChambersLiaisonManager": True},
                    "payment": {"paymentMethod": "CHECK"},
                    "advocate": {
                        "advocateLevel": "Junior",
                        "solicitorRegulationAuthorityRollNumber": "SRA1234",
                    },
                },
            },
        )

    def test_create_provider_firm_rejects_practitioner_without_parent_chambers(self, initialized_client):
        firm = Firm(
            firmName="TEST ADVOCATE",
            firmType="Advocate",
            solicitorAdvocateYN="Yes",
            advocateLevel="Junior",
            barCouncilRoll="SRA1234",
        )

        with pytest.raises(PDAError, match="A parent chambers firm is required"):
            initialized_client.create_provider_firm(firm)

    def test_create_provider_office_posts_then_hydrates(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client._handle_response = Mock(
            return_value={"data": {"officeCode": "ACC010", "providerFirmNumber": "100001"}}
        )
        initialized_client._get_provider_office_for_firm = Mock(
            return_value=Office(
                firmOfficeCode="ACC010",
                addressLine1="1 Test Way",
                city="Leeds",
                postCode="LS1 1AA",
                paymentMethod="CHECK",
            )
        )
        office = Office(
            officeName="Test Firm",
            addressLine1="1 Test Way",
            city="Leeds",
            postCode="LS1 1AA",
            paymentMethod="Cheque",
        )
        liaison_manager = Contact(
            vendorSiteId=1,
            firstName="Temp",
            lastName="Office",
            emailAddress="temp.office@example.com",
            telephoneNumber="01134960000",
        )

        result = initialized_client.create_provider_office(
            office,
            100001,
            liaison_manager=liaison_manager,
            contract_manager_guid="cm-guid-001",
        )

        initialized_client.post.assert_called_once_with(
            "/provider-firms/100001/offices",
            json={
                "address": {"line1": "1 Test Way", "townOrCity": "Leeds", "postcode": "LS1 1AA"},
                "payment": {"paymentMethod": "CHECK"},
                "liaisonManager": {
                    "firstName": "Temp",
                    "lastName": "Office",
                    "emailAddress": "temp.office@example.com",
                    "telephoneNumber": "01134960000",
                },
                "contractManager": {"contractManagerGUID": "cm-guid-001"},
            },
        )
        initialized_client._get_provider_office_for_firm.assert_called_once_with("100001", "ACC010")
        assert result.firm_office_code == "ACC010"

    def test_create_office_contact_posts_then_fetches_liaison_manager(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client._handle_response = Mock(return_value={"data": {"liaisonManagerGUID": "lm-guid-001"}})
        initialized_client.get_liaison_manager = Mock(
            return_value=Contact(
                vendorSiteId=1,
                firstName="Jane",
                lastName="Doe",
                emailAddress="jane@example.com",
                telephoneNumber="01134960000",
            )
        )
        initialized_client.get_provider_office = Mock(return_value=Office(firmOfficeId=9, firmOfficeCode="ACC001"))
        contact = Contact(
            vendorSiteId=1,
            firstName="Jane",
            lastName="Doe",
            emailAddress="jane@example.com",
            telephoneNumber="01134960000",
        )

        result = initialized_client.create_office_contact(100001, "ACC001", contact)

        initialized_client.post.assert_called_once_with(
            "/provider-firms/100001/offices/ACC001/liaison-managers",
            json={
                "firstName": "Jane",
                "lastName": "Doe",
                "emailAddress": "jane@example.com",
                "telephoneNumber": "01134960000",
            },
        )
        initialized_client.get_liaison_manager.assert_called_once_with("lm-guid-001")
        assert result.vendor_site_id == 9

    def test_get_list_of_contract_manager_names_maps_display_name(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(
            return_value={
                "data": {
                    "content": [
                        {
                            "guid": "cm-guid-001",
                            "contractManagerId": "CM001",
                            "firstName": "Alice",
                            "lastName": "Johnson",
                        }
                    ]
                }
            }
        )

        result = initialized_client.get_list_of_contract_manager_names()

        initialized_client.get.assert_called_once_with("/provider-contract-managers")
        assert result == [{"guid": "cm-guid-001", "contractManagerId": "CM001", "name": "Alice Johnson"}]

    def test_assign_contract_manager_to_office_posts_guid_then_hydrates(self, initialized_client):
        initialized_client.post = Mock(return_value=Mock(status_code=201))
        initialized_client._handle_response = Mock(return_value={"data": {"contractManagerId": "CM002"}})
        initialized_client._get_provider_office_for_firm = Mock(return_value=Office(firmOfficeCode="ACC001"))

        result = initialized_client.assign_contract_manager_to_office(100001, "ACC001", "cm-guid-002")

        initialized_client.post.assert_called_once_with(
            "/provider-firms/100001/offices/ACC001/contract-managers",
            json={"contractManagerGUID": "cm-guid-002"},
        )
        initialized_client._get_provider_office_for_firm.assert_called_once_with(100001, "ACC001")
        assert result.firm_office_code == "ACC001"

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

    def test_provider_name_exists(self, initialized_client):
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(
            return_value={"data": {"content": [{"name": "Test LSP"}, {"name": "Other Firm"}]}}
        )

        result = initialized_client.provider_name_exists("Test LSP")

        initialized_client.get.assert_called_once_with("/provider-firms", params={"name": "Test LSP"})
        assert result is True

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

    def test_get_head_office_enriches_contract_manager_when_office_payload_omits_it(self, initialized_client):
        initialized_client.get_provider_offices = Mock(return_value=[Office(firmOfficeCode="ACC001", headOffice="N/A")])
        initialized_client.get = Mock(return_value=Mock(status_code=200))
        initialized_client._handle_response = Mock(
            return_value={
                "data": {
                    "content": [
                        {
                            "guid": "cm-guid-001",
                            "contractManagerId": "CM001",
                            "firstName": "John",
                            "lastName": "Smith",
                            "linkedFlag": True,
                        }
                    ]
                }
            }
        )

        head_office = initialized_client.get_head_office(123)

        initialized_client.get.assert_called_once_with("/provider-firms/123/offices/ACC001/contract-managers")
        assert head_office is not None
        assert head_office.contract_manager == "John Smith"
        assert head_office.contract_manager_guid == "cm-guid-001"
        assert head_office.contract_manager_id == "CM001"

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
