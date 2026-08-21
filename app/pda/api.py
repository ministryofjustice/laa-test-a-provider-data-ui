import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional, Union

import requests
from pydantic import ValidationError
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from app.constants import FirmType, YesNo
from app.models import BankAccount, Contact, Firm, Office
from app.pda.errors import ProviderDataApiError, ProviderDataApiHttpError


class PDAError(ProviderDataApiError):
    """Base exception for Provider Data API errors."""

    pass


class PDAConnectionError(PDAError):
    """Raised when unable to connect to the Provider Data API."""

    pass


class PDACapabilityError(PDAError):
    """Raised when an operation is not currently supported by the configured Provider Data API."""

    pass


class ProviderDataApi:
    """
    Client for interacting with the Provider Data API.

    Provides methods to read provider firms, offices, users,
    and related data through a REST API.

    Will retry on unsuccessful requests.
    """

    RETRY_STRATEGY = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,  # We'll handle status codes ourselves
    )

    def __init__(self):
        self.app = None
        self.base_url: Optional[str] = None
        self.session = requests.Session()
        self.session.trust_env = False
        self.logger = logging.getLogger(__name__)
        self._initialized = False
        self._mock_fallback = None

    def init_app(self, app, base_url: str = None, api_key: str = None) -> None:
        """
        Initialize the API client with Flask app configuration.

        Args:
            app: Flask application instance
            base_url: Base URL for the Provider Data API
            api_key: API key for authentication

        Raises:
            ValueError: If base_url or api_key are not provided
        """
        if not base_url:
            raise ValueError("Must provide a base URL for the Provider Data API.")
        if not api_key:
            raise ValueError("Must provide an API key for the Provider Data API.")

        self.app = app
        self.base_url = base_url.rstrip("/")

        self.session.headers.update(
            {
                "X-Authorization": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        self._setup_session_adapter()

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["pda"] = self

        self._initialized = True
        self.logger.info(f"Provider Data API initialized with base URL: {self.base_url}")

    def _setup_session_adapter(self) -> None:
        """Setup HTTP adapter with retry strategy for the session."""
        adapter = HTTPAdapter(max_retries=self.RETRY_STRATEGY)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def test_connection(self) -> bool:
        """
        Test connection to the Provider Data API.

        Returns:
            bool: True if connection successful, False otherwise

        Raises:
            ProviderDataApiConnectionError: If connection fails
        """
        if not self._initialized:
            raise PDAError("API client not initialized. Call init_app() first.")

        try:
            response = self.get("/")  # TODO: See if we can get a better status endpoint
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Failed to connect to Provider Data API: {e}")
            raise PDAConnectionError(f"Connection test failed: {e}")

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make an HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response: The response object

        Raises:
            ProviderDataApiError: If the request fails
        """
        if not self._initialized:
            raise PDAError("API client not initialized. Call init_app() first.")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if params := kwargs.get("params"):
            self.logger.debug(f"{method} request to {url} with params: {params}")
        else:
            self.logger.debug(f"{method} request to {url}")

        try:
            response = self.session.request(method, url, **kwargs)
            self.logger.debug(f"Response: {response.status_code} from {url}")
            return response

        except requests.RequestException as e:
            self.logger.error(f"Request failed for {method} {url}: {e}")
            raise PDAError(f"Request failed: {e}")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """
        Make a GET request to the specified endpoint.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            requests.Response: The response object
        """
        return self._make_request("GET", endpoint, params=params)

    def patch(self, endpoint: str, json: Dict[str, Any] = None) -> requests.Response:
        """
        Make a PATCH request to the specified endpoint.

        Args:
            endpoint: API endpoint path
            json: Data to be sent as JSON

        Returns:
            requests.Response: The response object
        """
        return self._make_request("PATCH", endpoint, json=json)

    def post(self, endpoint: str, json: Dict[str, Any] = None) -> requests.Response:
        """
        Make a POST request to the specified endpoint.

        Args:
            endpoint: API endpoint path
            json: Data to be sent as JSON

        Returns:
            requests.Response: The response object
        """
        return self._make_request("POST", endpoint, json=json)

    def _handle_response(
        self, response: requests.Response, empty_return: Union[Dict, List, None]
    ) -> Union[Dict, List, None]:
        """
        Handle common response patterns.

        Args:
            response: The HTTP response
            empty_return: What to return for 204/404 responses

        Returns:
            Parsed JSON data, empty_return, or None

        Raises:
            ProviderDataApiError: For HTTP errors
        """
        if 200 <= response.status_code < 300:
            if response.status_code == 204:
                return empty_return
            try:
                return response.json()
            except ValueError as e:
                # Some successful API operations return no JSON body.
                if empty_return is not None:
                    return empty_return
                self.logger.error(f"Failed to parse JSON response: {e}")
                raise PDAError(f"Invalid JSON response: {e}")

        elif response.status_code in [204, 404]:
            # 204: No Content (successful but empty)
            # 404: Not Found (resource doesn't exist)
            self.logger.debug(f"Empty response ({response.status_code}) from {response.url}")
            return empty_return

        else:
            # Handle other HTTP errors
            self.logger.error(f"HTTP {response.status_code} error from {response.url}")
            response_data = None
            detail = None
            try:
                response_data = response.json()
                if isinstance(response_data, dict):
                    detail = response_data.get("detail") or response_data.get("title")
                    if not detail and isinstance(response_data.get("error"), dict):
                        detail = response_data["error"].get("errorCode")
            except ValueError:
                response_data = None
            try:
                response.raise_for_status()
            except requests.HTTPError as e:
                raise ProviderDataApiHttpError(response.status_code, detail or str(e), response_data) from e

    def _unwrap_data_envelope(self, data: Any) -> Any:
        """Return payload for both legacy and PDA-R2 style envelopes."""
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    def _extract_collection(self, data: Any, keys: List[str]) -> List[Dict[str, Any]]:
        """Extract list payload from legacy or PDA-R2 list responses."""
        payload = self._unwrap_data_envelope(data)

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            if isinstance(payload.get("content"), list):
                return payload["content"]

            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    @staticmethod
    def _int_or_default(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _normalize_firm_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Map PDA-R2 firm DTOs to the legacy Firm model shape."""
        if not isinstance(item, dict):
            return {}

        # Legacy shape is already compatible with model aliases.
        if "firmId" in item or "firmName" in item:
            normalized = dict(item)
            legal = normalized.get("legalServicesProvider") or {}

            if "constitutionalStatus" not in normalized:
                normalized["constitutionalStatus"] = legal.get("constitutionalStatus") or "N/A"

            company_house_number = (
                normalized.get("companyHouseNumber")
                or normalized.get("companiesHouseNumber")
                or legal.get("companyHouseNumber")
                or legal.get("companiesHouseNumber")
            )
            if company_house_number and "companyHouseNumber" not in normalized:
                normalized["companyHouseNumber"] = company_house_number

            if "indemnityReceivedDate" not in normalized and legal.get("indemnityReceivedDate"):
                normalized["indemnityReceivedDate"] = legal.get("indemnityReceivedDate")

            # Legacy model expects companyHouseNumber; discard API alias variant.
            normalized.pop("companiesHouseNumber", None)
            return {k: v for k, v in normalized.items() if v is not None}

        firm_number = item.get("firmNumber")
        firm_type = item.get("firmType")
        legal = item.get("legalServicesProvider") or {}
        practitioner = item.get("practitioner") or {}
        advocate = practitioner.get("advocate") or {}
        parent_firms = practitioner.get("parentFirms") or []
        first_parent = parent_firms[0] if parent_firms else {}

        solicitor_advocate = None
        if firm_type == "Advocate":
            solicitor_advocate = "Yes"
        elif firm_type == "Barrister":
            solicitor_advocate = "No"

        constitutional_status = legal.get("constitutionalStatus") or item.get("constitutionalStatus")
        if constitutional_status is None:
            constitutional_status = "N/A"

        company_house_number = (
            legal.get("companyHouseNumber")
            or legal.get("companiesHouseNumber")
            or item.get("companyHouseNumber")
            or item.get("companiesHouseNumber")
        )

        indemnity_received_date = legal.get("indemnityReceivedDate") or item.get("indemnityReceivedDate")

        normalized = {
            "firmNumber": str(firm_number) if firm_number is not None else "",
            "firmId": self._int_or_default(firm_number),
            "firmName": item.get("name") or item.get("firmName") or "",
            "firmType": firm_type,
            "constitutionalStatus": constitutional_status,
            "parentFirmId": self._int_or_default(first_parent.get("parentFirmNumber"), 0),
            "solicitorAdvocateYN": solicitor_advocate,
            "advocateLevel": advocate.get("advocateLevel"),
            "barCouncilRoll": advocate.get("barCouncilRollNumber")
            or advocate.get("solicitorRegulationAuthorityRollNumber"),
            "companyHouseNumber": company_house_number,
            "indemnityReceivedDate": indemnity_received_date,
            "holdAllPaymentsFlag": "N",
            "nonProfitOrganisation": "N/A",
            "smallBusinessFlag": "N",
            "womenOwnedFlag": "N",
            "inactiveDate": legal.get("activeDateTo"),
        }

        # Remove empty strings for optional text fields to avoid noisy model data.
        if not normalized["firmNumber"]:
            normalized.pop("firmNumber")
        if not normalized["firmName"]:
            normalized.pop("firmName")

        return normalized

    def _normalize_office_data(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Map PDA-R2 office DTOs to the legacy Office model shape."""
        if not isinstance(item, dict):
            return {}

        # Legacy shape is already compatible with model aliases.
        if "firmOfficeCode" in item or "firm_office_code" in item:
            return item

        address = item.get("address") or {}
        dx_details = item.get("dxDetails") or {}
        payment = item.get("payment") or {}
        vat_registration = item.get("vatRegistration") or {}
        intervened = item.get("intervened") or {}
        contract_manager = item.get("contractManager") or {}

        hold_all_payments_flag = None
        if payment.get("paymentHeldFlag") is not None:
            hold_all_payments_flag = "Y" if payment.get("paymentHeldFlag") else "N"

        debt_recovery_flag = None
        if item.get("debtRecoveryFlag") is not None:
            debt_recovery_flag = "Yes" if item.get("debtRecoveryFlag") else "No"

        account_number = item.get("accountNumber") or item.get("firmOfficeCode")
        office_numeric_id = 0
        if isinstance(account_number, str):
            digits = "".join(re.findall(r"\d+", account_number))
            office_numeric_id = self._int_or_default(digits, 0)

        normalized = {
            "firmOfficeId": office_numeric_id,
            "firmOfficeCode": item.get("accountNumber") or item.get("firmOfficeCode"),
            "officeName": item.get("name") or item.get("officeName") or item.get("accountNumber"),
            "addressLine1": address.get("line1"),
            "addressLine2": address.get("line2"),
            "addressLine3": address.get("line3"),
            "addressLine4": address.get("line4"),
            "city": address.get("townOrCity") or address.get("city"),
            "county": address.get("county"),
            "postCode": address.get("postcode"),
            "dxNumber": dx_details.get("dxNumber"),
            "dxCentre": dx_details.get("dxCentre"),
            "telephoneNumber": item.get("telephoneNumber"),
            "emailAddress": item.get("emailAddress"),
            "vatRegistrationNumber": vat_registration.get("vatNumber"),
            "headOffice": "N/A" if item.get("headOfficeFlag") else None,
            "paymentMethod": payment.get("paymentMethod"),
            "inactiveDate": item.get("activeDateTo"),
            "holdAllPaymentsFlag": hold_all_payments_flag,
            "holdReason": payment.get("paymentHeldReason"),
            "debtRecoveryFlag": debt_recovery_flag,
            "contractManager": " ".join(
                part for part in [contract_manager.get("firstName"), contract_manager.get("lastName")] if part
            )
            or contract_manager.get("contractManagerId"),
            "contract_manager_guid": contract_manager.get("guid"),
            "contract_manager_id": contract_manager.get("contractManagerId"),
            "intervenedDate": intervened.get("intervenedChangeDate") if intervened.get("intervenedFlag") else None,
        }

        return {k: v for k, v in normalized.items() if v is not None}

    def _get_primary_contract_manager_for_office(self, firm_id: int | str, office_code: str) -> Dict[str, Any] | None:
        """Get the currently linked contract manager for an office, when available."""
        response = self.get(f"/provider-firms/{firm_id}/offices/{office_code}/contract-managers")
        raw_data = self._handle_response(response, [])
        managers = self._extract_collection(raw_data, ["contractManagers"])
        if not managers:
            return None

        linked_manager = next((m for m in managers if isinstance(m, dict) and m.get("linkedFlag") is True), None)
        if linked_manager:
            return linked_manager

        first_manager = managers[0]
        return first_manager if isinstance(first_manager, dict) else None

    def _hydrate_office_contract_manager(self, firm_id: int | str, office: Office | None) -> Office | None:
        """Backfill contract manager details from the dedicated endpoint when office payload omits them."""
        if office is None or not office.firm_office_code:
            return office

        needs_name = not office.contract_manager or (
            office.contract_manager_id is not None and office.contract_manager == office.contract_manager_id
        )
        needs_metadata = not office.contract_manager_guid or not office.contract_manager_id
        if not needs_name and not needs_metadata:
            return office

        try:
            manager = self._get_primary_contract_manager_for_office(firm_id, office.firm_office_code)
        except PDAError as e:
            self.logger.warning(
                "Unable to enrich contract manager for firm %s office %s: %s",
                firm_id,
                office.firm_office_code,
                e,
            )
            return office

        if not manager:
            return office

        display_name = " ".join(part for part in [manager.get("firstName"), manager.get("lastName")] if part).strip()
        if not display_name:
            display_name = manager.get("contractManagerId")

        updates = {}
        if display_name and (not office.contract_manager or office.contract_manager == office.contract_manager_id):
            updates["contract_manager"] = display_name

        if manager.get("guid") and not office.contract_manager_guid:
            updates["contract_manager_guid"] = manager.get("guid")

        if manager.get("contractManagerId") and not office.contract_manager_id:
            updates["contract_manager_id"] = manager.get("contractManagerId")

        if not updates:
            return office

        return office.model_copy(update=updates)

    def _normalize_bank_account_data(self, item: Dict[str, Any], office_code: str) -> Dict[str, Any]:
        """Map PDA-R2 bank account DTOs to the legacy BankAccount model shape."""
        if not isinstance(item, dict):
            return {}

        raw_sort_code = item.get("sortCode")
        sort_code_digits = "".join(re.findall(r"\d", str(raw_sort_code or "")))
        if len(sort_code_digits) >= 6:
            normalized_sort_code = sort_code_digits[:6]
        elif 0 < len(sort_code_digits) < 6:
            normalized_sort_code = sort_code_digits.zfill(6)
        else:
            normalized_sort_code = "000000"

        if "bankAccountId" in item or "accountNumber" in item and "bankAccountName" in item:
            normalized_item = item.copy()
            normalized_item["sortCode"] = normalized_sort_code
            return normalized_item

        account_number = item.get("accountNumber")
        account_name = item.get("accountName") or "Unknown account"
        sort_code = normalized_sort_code
        primary_flag = item.get("primaryFlag")
        if isinstance(primary_flag, bool):
            primary_flag = "Y" if primary_flag else "N"
        elif isinstance(primary_flag, str):
            primary_flag = "Y" if primary_flag.strip().lower() in {"y", "yes", "true", "1"} else "N"
        else:
            primary_flag = "N"

        office_digits = "".join(re.findall(r"\d+", office_code or ""))
        vendor_site_id = self._int_or_default(office_digits, 1)

        guid_digits = "".join(re.findall(r"\d+", str(item.get("guid", ""))))
        bank_account_id = self._int_or_default(guid_digits, 1)

        return {
            "bankAccountId": bank_account_id,
            "vendorSiteId": vendor_site_id,
            "bankName": item.get("bankName") or "Unknown bank",
            "bankBranchName": item.get("bankBranchName") or "Unknown branch",
            "sortCode": sort_code,
            "accountNumber": account_number,
            "bankAccountName": account_name,
            "currencyCode": item.get("currencyCode") or "GBP",
            "accountType": item.get("accountType") or "Current",
            "primaryFlag": primary_flag,
            "startDate": item.get("activeDateFrom") or item.get("startDate") or date.today().isoformat(),
            "endDate": item.get("activeDateTo") or item.get("endDate"),
        }

    def _unsupported(self, message: str) -> None:
        """Raise a typed error for API features that are not yet supported."""
        raise PDACapabilityError(message)

    def _build_provider_create_payload(
        self,
        firm: Firm,
        office: Office | None = None,
        liaison_manager: Contact | None = None,
        bank_account: BankAccount | None = None,
        contract_manager_guid: str | None = None,
    ) -> Dict[str, Any]:
        if not isinstance(firm, Firm):
            raise ValueError("firm must be a Firm instance")

        payload: Dict[str, Any] = {
            "name": firm.firm_name,
            "firmType": "Advocate" if firm.is_barrister else firm.firm_type,
        }

        if firm.is_legal_services_provider:
            legal_services_provider: Dict[str, Any] = {
                "constitutionalStatus": firm.constitutional_status,
            }
            if office and liaison_manager:
                legal_services_provider["address"] = {
                    "line1": office.address_line_1,
                    "townOrCity": office.city,
                    "postcode": office.postcode,
                }
                optional_address = {
                    "line2": office.address_line_2,
                    "line3": office.address_line_3,
                    "line4": office.address_line_4,
                    "county": office.county,
                }
                for key, value in optional_address.items():
                    if value:
                        legal_services_provider["address"][key] = value

                payment: Dict[str, Any] = {"paymentMethod": self._map_payment_method(office.payment_method)}
                if bank_account and payment["paymentMethod"] == "EFT":
                    payment["bankAccountDetails"] = {
                        "accountName": bank_account.bank_account_name,
                        "sortCode": bank_account.sort_code,
                        "accountNumber": bank_account.account_number,
                    }
                legal_services_provider["payment"] = payment

                legal_services_provider["liaisonManager"] = {
                    "firstName": liaison_manager.first_name,
                    "lastName": liaison_manager.last_name,
                    "emailAddress": liaison_manager.email_address,
                    "telephoneNumber": liaison_manager.telephone_number,
                }
                if contract_manager_guid:
                    legal_services_provider["contractManager"] = {"contractManagerGUID": contract_manager_guid}
                else:
                    legal_services_provider["contractManager"] = None

                optional_contact_fields = {
                    "telephoneNumber": office.telephone_number,
                    "emailAddress": office.email_address,
                }
                for key, value in optional_contact_fields.items():
                    if value:
                        legal_services_provider[key] = value

                if office.dx_number and office.dx_centre:
                    legal_services_provider["dxDetails"] = {
                        "dxNumber": office.dx_number,
                        "dxCentre": office.dx_centre,
                    }

                if office.vat_registration_number:
                    legal_services_provider["vatRegistration"] = {
                        "vatNumber": office.vat_registration_number,
                    }
            if firm.indemnity_received_date is not None:
                legal_services_provider["indemnityReceivedDate"] = str(firm.indemnity_received_date)
            if firm.company_house_number:
                legal_services_provider["companiesHouseNumber"] = firm.company_house_number
            payload["legalServicesProvider"] = legal_services_provider
            return payload

        if firm.is_chambers:
            chambers: Dict[str, Any] = {}
            if office and liaison_manager:
                chambers["address"] = {
                    "line1": office.address_line_1,
                    "townOrCity": office.city,
                    "postcode": office.postcode,
                }
                optional_address = {
                    "line2": office.address_line_2,
                    "line3": office.address_line_3,
                    "line4": office.address_line_4,
                    "county": office.county,
                }
                for key, value in optional_address.items():
                    if value:
                        chambers["address"][key] = value

                chambers["liaisonManager"] = {
                    "firstName": liaison_manager.first_name,
                    "lastName": liaison_manager.last_name,
                    "emailAddress": liaison_manager.email_address,
                    "telephoneNumber": liaison_manager.telephone_number,
                }
                chambers["contractManager"] = None

                optional_contact_fields = {
                    "telephoneNumber": office.telephone_number,
                    "emailAddress": office.email_address,
                }
                for key, value in optional_contact_fields.items():
                    if value:
                        chambers[key] = value

                if liaison_manager.website:
                    chambers["website"] = liaison_manager.website
                if office.dx_number and office.dx_centre:
                    chambers["dxDetails"] = {
                        "dxNumber": office.dx_number,
                        "dxCentre": office.dx_centre,
                    }
            payload["chambers"] = chambers
            return payload

        if firm.parent_firm_id <= 0:
            raise PDAError("A parent chambers firm is required when creating an advocate or barrister")

        practitioner: Dict[str, Any] = {
            "advocateType": "Barrister" if firm.is_barrister else "Advocate",
            "parentFirms": [{"parentFirmNumber": str(firm.parent_firm_id)}],
            # Practitioner creation uses parent's chambers liaison manager.
            "liaisonManager": {"useChambersLiaisonManager": True},
            # Practitioner payload must include payment details; default to cheque/check.
            "payment": {"paymentMethod": "CHECK"},
        }

        advocate_details: Dict[str, Any] = {}
        if firm.advocate_level:
            advocate_details["advocateLevel"] = firm.advocate_level
        if firm.bar_council_roll:
            roll_field = "barCouncilRollNumber" if firm.is_barrister else "solicitorRegulationAuthorityRollNumber"
            advocate_details[roll_field] = firm.bar_council_roll
        if advocate_details:
            if firm.is_barrister:
                practitioner["barrister"] = advocate_details
            else:
                practitioner["advocate"] = advocate_details

        payload["practitioner"] = practitioner
        return payload

    def create_provider_firm(
        self,
        firm: Firm,
        office: Office | None = None,
        liaison_manager: Contact | None = None,
        bank_account: BankAccount | None = None,
        contract_manager_guid: str | None = None,
    ) -> Firm:
        payload = self._build_provider_create_payload(
            firm,
            office=office,
            liaison_manager=liaison_manager,
            bank_account=bank_account,
            contract_manager_guid=contract_manager_guid,
        )
        response = self.post("/provider-firms", json=payload)
        raw_data = self._handle_response(response, {})
        payload_data = self._unwrap_data_envelope(raw_data)

        if not isinstance(payload_data, dict):
            raise PDAError("Invalid create provider response payload")

        provider_identifier = payload_data.get("providerFirmNumber") or payload_data.get("providerFirmGUID")
        if not provider_identifier:
            raise PDAError("Create provider response did not include a provider identifier")

        # PDA-R2 can omit persisting top-level LSP details on create when submitting the
        # nested onboarding payload. Apply a follow-up patch to guarantee these values.
        if firm.is_legal_services_provider and office is not None:
            lsp_details_patch: Dict[str, Any] = {}
            if firm.constitutional_status and firm.constitutional_status != "N/A":
                lsp_details_patch["constitutionalStatus"] = firm.constitutional_status
            if firm.indemnity_received_date not in (None, ""):
                lsp_details_patch["indemnityReceivedDate"] = str(firm.indemnity_received_date)
            if firm.company_house_number:
                lsp_details_patch["companiesHouseNumber"] = firm.company_house_number

            if lsp_details_patch:
                try:
                    patch_response = self.patch(
                        f"/provider-firms/{provider_identifier}",
                        json={"legalServicesProvider": lsp_details_patch},
                    )
                    self._handle_response(patch_response, {})
                except ProviderDataApiHttpError as e:
                    self.logger.warning(
                        "Post-create LSP details patch failed for provider %s (status=%s): %s",
                        provider_identifier,
                        e.status_code,
                        e,
                    )

        created_firm = self.get_provider_firm(str(provider_identifier))
        if not created_firm:
            raise PDAError(f"Created provider {provider_identifier} could not be retrieved")
        return created_firm

    @staticmethod
    def _map_payment_method(payment_method: str | None) -> str:
        mapping = {
            "electronic": "EFT",
            "eft": "EFT",
            "cheque": "CHECK",
            "check": "CHECK",
        }
        normalized = (payment_method or "CHECK").strip().lower()
        return mapping.get(normalized, payment_method or "CHECK")

    def _find_contract_manager_by_name(self, name: str) -> Dict[str, Any] | None:
        if not name:
            return None
        normalized_name = name.strip().lower()
        for manager in self.get_list_of_contract_manager_names():
            if manager.get("name", "").strip().lower() == normalized_name:
                return manager
        return None

    def _build_provider_office_create_payload(
        self,
        office: Office,
        liaison_manager: Contact,
        contract_manager_guid: str | None = None,
    ) -> Dict[str, Any]:
        if not contract_manager_guid and office.contract_manager_guid:
            contract_manager_guid = office.contract_manager_guid
        if not contract_manager_guid and office.contract_manager:
            manager = self._find_contract_manager_by_name(office.contract_manager)
            contract_manager_guid = manager.get("guid") if manager else None

        payload: Dict[str, Any] = {
            "address": {
                "line1": office.address_line_1,
                "townOrCity": office.city,
                "postcode": office.postcode,
            },
            "payment": {"paymentMethod": self._map_payment_method(office.payment_method)},
            "liaisonManager": {
                "firstName": liaison_manager.first_name,
                "lastName": liaison_manager.last_name,
                "emailAddress": liaison_manager.email_address,
                "telephoneNumber": liaison_manager.telephone_number,
            },
            "contractManager": {"contractManagerGUID": contract_manager_guid} if contract_manager_guid else {},
        }

        optional_address = {
            "line2": office.address_line_2,
            "line3": office.address_line_3,
            "line4": office.address_line_4,
            "county": office.county,
        }
        for key, value in optional_address.items():
            if value:
                payload["address"][key] = value

        optional_office = {
            "telephoneNumber": office.telephone_number,
            "emailAddress": office.email_address,
        }
        for key, value in optional_office.items():
            if value:
                payload[key] = value

        if office.dx_number and office.dx_centre:
            payload["dxDetails"] = {"dxNumber": office.dx_number, "dxCentre": office.dx_centre}

        return payload

    def _get_provider_office_for_firm(self, firm_id: int | str, office_code: str) -> Office | None:
        response = self.get(f"/provider-firms/{firm_id}/offices/{office_code}")
        raw_data = self._handle_response(response, None)
        if raw_data is None:
            return None
        try:
            payload = self._unwrap_data_envelope(raw_data)
            office = payload.get("office", payload) if isinstance(payload, dict) else payload
            office = self._normalize_office_data(office)
            normalized_office = Office(**office)
            return self._hydrate_office_contract_manager(firm_id, normalized_office)
        except ValidationError as e:
            self.logger.error(f"Invalid office data from API for office {office_code}: {e}")
            raise PDAError(f"Invalid office data: {e}")

    def create_provider_office(
        self,
        office: Office,
        firm_id: int,
        liaison_manager: Contact | None = None,
        contract_manager_guid: str | None = None,
    ) -> Office:
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if liaison_manager is None:
            raise PDAError("liaison_manager is required to create an office with the real Provider Data API")

        payload = self._build_provider_office_create_payload(office, liaison_manager, contract_manager_guid)
        response = self.post(f"/provider-firms/{firm_id}/offices", json=payload)
        raw_data = self._handle_response(response, {})
        payload_data = self._unwrap_data_envelope(raw_data)
        if not isinstance(payload_data, dict):
            raise PDAError("Invalid create office response payload")

        office_code = payload_data.get("officeCode")
        provider_identifier = payload_data.get("providerFirmNumber") or payload_data.get("providerFirmGUID") or firm_id
        if not office_code:
            raise PDAError("Create office response did not include an office code")

        created_office = self._get_provider_office_for_firm(provider_identifier, office_code)
        if not created_office:
            raise PDAError(f"Created office {office_code} could not be retrieved")
        return created_office

    def get_liaison_manager(self, liaison_manager_guid: str) -> Contact:
        if not liaison_manager_guid or not isinstance(liaison_manager_guid, str):
            raise ValueError("liaison_manager_guid must be a non-empty string")

        response = self.get(f"/provider-liaison-managers/{liaison_manager_guid}")
        raw_data = self._handle_response(response, {})
        payload = self._unwrap_data_envelope(raw_data)
        if not isinstance(payload, dict):
            raise PDAError("Invalid liaison manager response payload")

        return Contact(
            vendorSiteId=1,
            firstName=payload.get("firstName") or "",
            lastName=payload.get("lastName") or "",
            emailAddress=payload.get("emailAddress") or "unknown@example.com",
            telephoneNumber=payload.get("telephoneNumber"),
            website=None,
            jobTitle="Liaison manager",
            primary="Y",
            activeFrom=payload.get("activeDateFrom"),
        )

    def get_provider_firm(self, firm_id: int | str) -> Firm | None:
        """
        Get details for a specific provider firm.

        Args:
            firm_id: The firm ID

        Returns:
            Firm model instance, or None if not found
        """
        if isinstance(firm_id, int):
            if firm_id <= 0:
                raise ValueError("firm_id must be a positive integer or non-empty string")
        elif isinstance(firm_id, str):
            if not firm_id.strip():
                raise ValueError("firm_id must be a positive integer or non-empty string")
        else:
            raise ValueError("firm_id must be a positive integer or non-empty string")

        response = self.get(f"/provider-firms/{firm_id}")
        raw_data = self._handle_response(response, None)

        if raw_data is None:
            return None

        try:
            payload = self._unwrap_data_envelope(raw_data)
            firm = payload.get("firm") if isinstance(payload, dict) else None
            if firm is None and isinstance(payload, dict):
                firm = payload.get("providerFirm", payload)
            firm = self._normalize_firm_data(firm)
            return Firm(**firm)
        except ValidationError as e:
            self.logger.error(f"Invalid firm data from API for firm {firm_id}: {e}")
            raise PDAError(f"Invalid firm data: {e}")

    def get_all_provider_firms(self) -> List[Firm]:
        """
        Get all provider firms.

        Returns:
            List of Firm model instances
        """
        response = self.get("/provider-firms")
        raw_data = self._handle_response(response, [])

        if not raw_data:
            return []

        try:
            firms = self._extract_collection(raw_data, ["firms", "providerFirms"])
            normalized_firms = []
            for firm_data in firms:
                unwrapped = firm_data.get("firm") if isinstance(firm_data, dict) and "firm" in firm_data else firm_data
                normalized_firms.append(Firm(**self._normalize_firm_data(unwrapped)))
            return normalized_firms
        except ValidationError as e:
            self.logger.error(f"Invalid firms data from API: {e}")
            raise PDAError(f"Invalid firms data: {e}")

    def provider_name_exists(self, name: str) -> bool:
        if not name or not isinstance(name, str):
            return False

        response = self.get("/provider-firms", params={"name": name})
        raw_data = self._handle_response(response, [])
        firms = self._extract_collection(raw_data, ["firms", "providerFirms"])
        normalized_name = re.sub(r"[^a-z0-9]", "", name.strip().lower())

        for firm in firms:
            candidate = firm.get("name") or firm.get("firmName")
            if not candidate:
                continue
            normalized_candidate = re.sub(r"[^a-z0-9]", "", str(candidate).strip().lower())
            if normalized_candidate == normalized_name:
                return True

        return False

    def search_provider_firms(self, search_term: str) -> List[Firm]:
        """Search providers by name using backend filtering when available."""
        if not search_term or not isinstance(search_term, str):
            return []

        response = self.get("/provider-firms", params={"name": search_term})
        raw_data = self._handle_response(response, [])
        if not raw_data:
            return []

        try:
            firms = self._extract_collection(raw_data, ["firms", "providerFirms"])
            normalized_firms = []
            for firm_data in firms:
                unwrapped = firm_data.get("firm") if isinstance(firm_data, dict) and "firm" in firm_data else firm_data
                normalized_firms.append(Firm(**self._normalize_firm_data(unwrapped)))
            return normalized_firms
        except ValidationError as e:
            self.logger.error(f"Invalid firms data from API search for term {search_term}: {e}")
            raise PDAError(f"Invalid firms data: {e}")

    def get_provider_office(self, office_code: str, firm_id: int | None = None) -> Office | None:
        """
        Get details for a specific provider office.

        Args:
            office_code: The office code
            firm_id: Optional provider firm ID used for OpenAPI-first lookup

        Returns:
            Office model instance, or None if not found
        """
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")
        if firm_id is not None and (not isinstance(firm_id, int) or firm_id <= 0):
            raise ValueError("firm_id must be a positive integer")

        raw_data = None

        if firm_id is not None:
            response = self.get(f"/provider-firms/{firm_id}/offices/{office_code}")
            raw_data = self._handle_response(response, None)
            if raw_data is None:
                self.logger.warning(
                    "OpenAPI office detail lookup returned no data for firm %s office %s; falling back to legacy endpoint.",
                    firm_id,
                    office_code,
                )
        else:
            self.logger.warning(
                "Office lookup called without firm_id for office %s; using legacy endpoint fallback path.",
                office_code,
            )

        if raw_data is None:
            fallback_response = self.get(f"/provider-offices/{office_code}")
            raw_data = self._handle_response(fallback_response, None)

        if raw_data is None:
            self.logger.warning(
                "Legacy office detail lookup returned no data for office %s; falling back to legacy office search endpoint.",
                office_code,
            )
            fallback_response = self.get("/provider-firms-offices", params={"officeCode": office_code, "pageSize": 1})
            fallback_data = self._handle_response(fallback_response, [])
            offices = self._extract_collection(fallback_data, ["offices"])
            raw_data = offices[0] if offices else None

        if raw_data is None:
            self.logger.warning(
                "No office data found for office %s%s after OpenAPI and legacy fallbacks.",
                office_code,
                f" (firm {firm_id})" if firm_id is not None else "",
            )
            return None

        try:
            payload = self._unwrap_data_envelope(raw_data)
            office = payload.get("office", payload) if isinstance(payload, dict) else payload
            office = self._normalize_office_data(office)
            return Office(**office)
        except ValidationError as e:
            self.logger.error(f"Invalid office data from API for office {office_code}: {e}")
            raise PDAError(f"Invalid office data: {e}")

    def get_provider_offices(self, firm_id: int) -> List[Office]:
        """
        Get all offices for a specific firm.

        Args:
            firm_id: The firm ID

        Returns:
            List of FirmOffice model instances
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")

        response = self.get(f"/provider-firms/{firm_id}/offices")
        raw_data = self._handle_response(response, [])

        offices_data = self._extract_collection(raw_data, ["offices"])
        if not offices_data:
            self.logger.warning(
                "OpenAPI office list lookup returned no data for firm %s; falling back to legacy endpoint.",
                firm_id,
            )
            fallback_response = self.get(f"/provider-firms/{firm_id}/provider-offices")
            fallback_data = self._handle_response(fallback_response, [])
            offices_data = self._extract_collection(fallback_data, ["offices"])

        if not offices_data:
            self.logger.warning(
                "No offices found for firm %s after OpenAPI and legacy fallbacks.",
                firm_id,
            )
            return []

        try:
            return [Office(**self._normalize_office_data(office_data)) for office_data in offices_data]
        except ValidationError as e:
            self.logger.error(f"Invalid offices data from API for firm {firm_id}: {e}")
            raise PDAError(f"Invalid offices data: {e}")

    def get_head_office(self, firm_id: int) -> Office | None:
        """
        Gets the head office for a specific firm.

        Args:
            firm_id: The firm ID

        Returns:
            FirmOffice model instance for the head office, or None if not found
        """
        offices = self.get_provider_offices(firm_id)

        if not offices:
            return None

        for office in offices:
            # Child offices have headOffice = parent's office ID
            # Head offices have headOffice = "N/A"
            if office.head_office == "N/A":
                return self._hydrate_office_contract_manager(firm_id, office)

        # Some backends don't explicitly mark head office for single-office firms.
        if len(offices) == 1:
            return self._hydrate_office_contract_manager(firm_id, offices[0])

        return None

    def get_provider_users(self, firm_id: int) -> List[Dict[str, Any]]:
        """
        Get all users for a specific firm.

        Args:
            firm_id: The firm ID (changed from str to int for consistency)

        Returns:
            List of dictionaries containing user details
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")

        response = self.get(f"/provider-firms/{firm_id}/provider-users")
        return self._handle_response(response, [])

    def get_provider_children(self, firm_id: int, only_firm_type: FirmType | None = None) -> List[Firm]:
        """
        Get child provider firms for a given parent firm.

        This method uses the full firm list and filters locally so that mock and
        real API clients expose a compatible interface.
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")

        firms = self.get_all_provider_firms()
        children: List[Firm] = []
        for firm in firms:
            if firm.parent_firm_id != firm_id:
                continue
            if only_firm_type is not None and firm.firm_type != only_firm_type:
                continue
            children.append(firm)
        return children

    def get_office_contract_details(self, firm_id: int, office_code: str) -> Optional[Dict[str, Any]]:
        """
        Get contract details for a specific office.

        Args:
            firm_id: The firm ID
            office_code: The office code

        Returns:
            Dict containing contract details
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")

        response = self.get(f"/provider-firms/{firm_id}/provider-offices/{office_code}/office-contract-details")
        data = self._handle_response(response, {})
        payload = self._unwrap_data_envelope(data)
        return payload if isinstance(payload, dict) else {}

    def get_office_schedule_details(self, firm_id: int, office_code: str) -> Optional[Dict[str, Any]]:
        """
        Get schedule details for a specific office.

        Args:
            firm_id: The firm ID
            office_code: The office code

        Returns:
            Dict containing schedule details
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")

        response = self.get(f"/provider-firms/{firm_id}/provider-offices/{office_code}/schedules")
        data = self._handle_response(response, {})
        payload = self._unwrap_data_envelope(data)
        return payload if isinstance(payload, dict) else {}

    def get_office_bank_accounts(self, firm_id: int, office_code: str) -> List[BankAccount]:
        """
        Get bank details for a specific office.

        Args:
            firm_id: The firm ID
            office_code: The office code

        Returns:
            List of BankAccount model instances
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")

        response = self.get(f"/provider-firms/{firm_id}/provider-offices/{office_code}/bank-account-details")
        data = self._handle_response(response, [])

        items = self._extract_collection(data, ["bankAccounts", "bankAccountDetails"])
        if not items:
            fallback_response = self.get(f"/provider-firms/{firm_id}/offices/{office_code}/bank-details")
            fallback_data = self._handle_response(fallback_response, [])
            items = self._extract_collection(fallback_data, ["bankAccounts", "bankAccountDetails"])

        bank_accounts = []
        if items:
            for bank_account in items:
                bank_accounts.append(BankAccount(**self._normalize_bank_account_data(bank_account, office_code)))
        return bank_accounts

    def patch_office(self, firm_id: int, office_code: str, fields_to_update: dict):
        response = self.patch(
            f"/provider-firms/{firm_id}/offices/{office_code}",
            json=fields_to_update,
        )
        return self._handle_response(response, {})

    @staticmethod
    def _to_bool(value: Any) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"yes", "y", "true", "1"}:
                return True
            if normalized in {"no", "n", "false", "0"}:
                return False
        return None

    def update_office_payment_method(self, firm_id: int, office_code: str, payment_method: str) -> Office:
        if not payment_method or not isinstance(payment_method, str):
            raise ValueError("payment_method must be a non-empty string")

        payment_method_lookup = {
            "electronic": "EFT",
            "eft": "EFT",
            "cheque": "CHECK",
            "check": "CHECK",
        }
        mapped_payment_method = payment_method_lookup.get(payment_method.strip().lower(), payment_method)

        self.patch_office(firm_id, office_code, {"paymentMethod": mapped_payment_method})
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office

    def patch_provider_firm(self, firm_id: int, fields_to_update: dict) -> Firm | None:
        return self.patch_provider(firm_id, fields_to_update)

    def get_office_contacts(self, firm_id: int, office_code: str) -> List[Contact]:
        """
        Get all contacts for a specific office.

        Args:
            firm_id: The firm ID
            office_code: The office code

        Returns:
            List of Contact model instances

        Raises:
            NotImplementedError: This functionality is not yet supported by the real API
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")

        response = self.get(f"/provider-firms/{firm_id}/offices/{office_code}/liaison-managers")
        raw_data = self._handle_response(response, [])
        managers = self._extract_collection(raw_data, ["liaisonManagers"])
        if not managers:
            return []

        office = self.get_provider_office(office_code, firm_id=firm_id)
        vendor_site_id = office.firm_office_id if office and office.firm_office_id > 0 else 1

        contacts: List[Contact] = []
        for manager in managers:
            try:
                contacts.append(
                    Contact(
                        vendorSiteId=vendor_site_id,
                        firstName=manager.get("firstName") or "",
                        lastName=manager.get("lastName") or "",
                        emailAddress=manager.get("emailAddress") or "unknown@example.com",
                        telephoneNumber=manager.get("telephoneNumber"),
                        website=None,
                        jobTitle="Liaison manager",
                        primary="Y" if manager.get("linkedFlag", True) else "N",
                        activeFrom=manager.get("activeDateFrom"),
                    )
                )
            except ValidationError as e:
                self.logger.error(f"Invalid liaison manager data for office {office_code}: {e}")

        return contacts

    def create_office_contact(self, firm_id: int, office_code: str, contact: Contact) -> Contact:
        """
        Create a contact for an office.

        Args:
            firm_id: The firm ID
            office_code: The office code
            contact: Contact model instance to create

        Returns:
            Contact: The created Contact model instance

        Raises:
            NotImplementedError: This functionality is not yet supported by the real API
        """
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")

        payload = {
            "firstName": contact.first_name,
            "lastName": contact.last_name,
            "emailAddress": contact.email_address,
            "telephoneNumber": contact.telephone_number,
        }
        response = self.post(f"/provider-firms/{firm_id}/offices/{office_code}/liaison-managers", json=payload)
        raw_data = self._handle_response(response, {})
        payload_data = self._unwrap_data_envelope(raw_data)
        if not isinstance(payload_data, dict):
            raise PDAError("Invalid create liaison manager response payload")

        liaison_manager_guid = payload_data.get("liaisonManagerGUID")
        if not liaison_manager_guid:
            raise PDAError("Create liaison manager response did not include a liaison manager GUID")

        created_contact = self.get_liaison_manager(liaison_manager_guid)
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if office and office.firm_office_id > 0:
            created_contact = created_contact.model_copy(update={"vendor_site_id": office.firm_office_id})
        return created_contact

    def update_contact(self, firm_id: int, office_code: str, contact: Contact) -> Contact:
        """
        Update an existing contact.

        Args:
            firm_id: The firm ID
            office_code: The office code
            contact: Contact model instance with updated data

        Returns:
            Contact: The updated Contact model instance

        Raises:
            NotImplementedError: This functionality is not yet supported by the real API
        """
        self._unsupported("Updating contacts is not yet supported by the real Provider Data API")

    def patch_provider(self, firm_id: int, fields_to_update: dict):
        response = self.patch(
            f"/provider-firms/{firm_id}",
            json=fields_to_update,
        )
        self._handle_response(response, {})
        return self.get_provider_firm(firm_id)

    def assign_bank_account_to_office(self, firm_id: int, office_code: str, bank_account_id: int) -> BankAccount:
        """
        Assign a bank account to a specific office.

        Args:
            firm_id: The firm ID that the office belongs to
            office_code: The office code
            bank_account_id: The bank account ID to assign the office to

        Returns:
        """
        self._unsupported("Assigning bank account is not yet supported by the real Provider Data API")

    def get_bank_details(self, firm_id, bank_account_id: str) -> Optional[BankAccount]:
        response = self.get(f"/provider-firms/{firm_id}/bank-details/{bank_account_id}")
        data = self._handle_response(response, {})
        return BankAccount(**data)

    def get_provider_firm_bank_details(self, firm_id: int) -> List[BankAccount]:
        """
        Get all bank details for a specific provider.

        Args:
            firm_id: The id of the firm to get bank details for

        Returns:
            List[BankAccount]: List of bank accounts that belong to the given firm.
        """
        response = self.get(f"/provider-firms/{firm_id}/bank-account-details")
        items = self._handle_response(response, [])
        items = self._extract_collection(items, ["bankAccounts", "bankAccountDetails"])
        if not items:
            fallback_response = self.get(f"/provider-firms/{firm_id}/bank-details")
            fallback_data = self._handle_response(fallback_response, [])
            items = self._extract_collection(fallback_data, ["bankAccounts", "bankAccountDetails"])
        accounts = []
        for item in items:
            accounts.append(BankAccount(**self._normalize_bank_account_data(item, "")))
        return accounts

    def update_office_contact_details(self, firm_id, firm_office_code, payload):
        self.patch_office(firm_id, firm_office_code, payload)
        office = self.get_provider_office(firm_office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {firm_office_code} not found for firm {firm_id}")
        return office

    def add_bank_account_to_office(self, firm_id: int, office_code: str, bank_account: BankAccount) -> BankAccount:
        """
        Add a bank account to a specific office.

        Args:
            firm_id: Firm Id of the firm that the office belongs to
            office_code: The office code to add the bank account to
            bank_account: The bank account to add

        Returns:
            BankAccount: The bank account added to the given office
        """
        self._unsupported("Adding bank account to an office is not yet supported by the real Provider Data API")

    def get_all_bank_accounts(self) -> List[BankAccount]:
        """
        Get all bank accounts.
        Returns: List[BankAccount]
        """
        self._unsupported("Getting all bank accounts is currently not supported by the real Provider Data API")

    def update_provider_firm_name(self, firm_id: int, new_firm_name: str) -> Firm:
        """
        Update an existing firm name.
        Args:
            firm_id: The firm ID of the firm to update
            new_firm_name: The new firm name
        Returns: Firm
        """
        firm = self.patch_provider(firm_id, {"firmName": new_firm_name})
        if not firm:
            raise PDAError(f"Firm {firm_id} not found")
        return firm

    def update_legal_service_provider_details(self, firm_id: int, data: dict):
        firm = self.patch_provider(firm_id, data)
        if not firm:
            raise PDAError(f"Firm {firm_id} not found")
        return firm

    def update_barrister_details(self, firm_id, barrister_details: dict) -> Firm:
        """
        Update an existing barrister details.
        Args:
            firm_id: Firm Id of the firm that the office belongs to
            barrister_details: A dict of fields to update

        Returns: Firm
        """
        firm = self.patch_provider(firm_id, barrister_details)
        if not firm:
            raise PDAError(f"Firm {firm_id} not found")
        return firm

    def update_advocate_details(self, firm_id, advocate_details: dict) -> Firm:
        """
        Update an existing advocate details.
        Args:
            firm_id: The advocate firm Id
            advocate_details: A dict of fields to update

        Returns: Firm
        """
        firm = self.patch_provider(firm_id, advocate_details)
        if not firm:
            raise PDAError(f"Firm {firm_id} not found")
        return firm

    def update_office_false_balance(self, firm_id: int, office_code: str, data: dict) -> Office:
        """
        Update an existing office false balance.
        Args:
            firm_id: Firm Id of the firm that the office belongs to
            office_code: The code of the office to update
            data: a dict containing the office false balance

        Returns: Office
        """
        self.patch_office(firm_id, office_code, data)
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office

    def update_office_intervened_date(self, firm_id: int, office_code: str, data: dict) -> Office:
        """
        Update an existing office intervened date.
        Args:
            firm_id: Firm Id of the firm that the office belongs to
            office_code: The code of the office to update
            data: a dict containing the intervened date

        Returns: Office
        """
        payload = data.copy()
        if "intervenedDate" in payload:
            payload["intervenedFlag"] = payload["intervenedDate"] is not None
            payload["intervenedChangeDate"] = payload["intervenedDate"]
        self.patch_office(firm_id, office_code, payload)
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office

    def get_list_of_contract_manager_names(self):
        """Get a list of all known contract managers."""
        response = self.get("/provider-contract-managers")
        raw_data = self._handle_response(response, [])
        managers = self._extract_collection(raw_data, ["contractManagers"])

        results = []
        for manager in managers:
            first_name = manager.get("firstName") or ""
            last_name = manager.get("lastName") or ""
            results.append(
                {
                    "guid": manager.get("guid"),
                    "contractManagerId": manager.get("contractManagerId"),
                    "name": " ".join(part for part in [first_name, last_name] if part).strip()
                    or manager.get("contractManagerId")
                    or "Unknown contract manager",
                }
            )
        return results

    def assign_contract_manager_to_office(self, firm_id: int, office_code: str, contract_manager_guid: str) -> Office:
        if not isinstance(firm_id, int) or firm_id <= 0:
            raise ValueError("firm_id must be a positive integer")
        if not office_code or not isinstance(office_code, str):
            raise ValueError("office_code must be a non-empty string")
        if not contract_manager_guid or not isinstance(contract_manager_guid, str):
            raise ValueError("contract_manager_guid must be a non-empty string")

        response = self.post(
            f"/provider-firms/{firm_id}/offices/{office_code}/contract-managers",
            json={"contractManagerGUID": contract_manager_guid},
        )
        self._handle_response(response, {})
        office = self._get_provider_office_for_firm(firm_id, office_code)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office

    def update_office_debt_recovery(self, firm_id: int, office_code: str, data: dict | YesNo) -> Office:
        """
        Update an existing office debt recovery.
        Args:
            firm_id: The advocate firm Id
            office_code: The code of the office to update
            data: a dict containing the office fields to update

        Returns: Office
        """
        payload = data.copy() if isinstance(data, dict) else {"debtRecoveryFlag": data}
        if "debtRecoveryFlag" in payload:
            bool_value = self._to_bool(payload.get("debtRecoveryFlag"))
            if bool_value is not None:
                payload["debtRecoveryFlag"] = bool_value
        self.patch_office(firm_id, office_code, payload)
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office

    def update_office_hold_payments(self, firm_id: int, office_code: str, data: dict) -> Office:
        """
        Update an existing office payments on hold.
        Args:
            firm_id: Firm Id of the firm that the office belongs to
            office_code: The code of the office to update
            data: a dict containing the choise to hold payments

        Returns: Office
        """
        payload = data.copy()
        if "holdAllPaymentsFlag" in payload:
            bool_value = self._to_bool(payload.get("holdAllPaymentsFlag"))
            if bool_value is not None:
                payload["holdAllPaymentsFlag"] = bool_value
        self.patch_office(firm_id, office_code, payload)
        office = self.get_provider_office(office_code, firm_id=firm_id)
        if not office:
            raise PDAError(f"Office {office_code} not found for firm {firm_id}")
        return office
