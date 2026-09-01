import re

from flask import current_app, session
from wtforms import RadioField, SubmitField, ValidationError
from wtforms.fields.simple import StringField
from wtforms.validators import Email, InputRequired, Length, Optional

from app.components.tables import RadioDataTable, TableStructureItem
from app.constants import (
    ADVOCATE_LEVEL_CHOICES,
    CONSTITUTIONAL_STATUS_CHOICES,
    PARENT_FIRM_TYPE_CHOICES,
    YES_NO_CHOICES,
)
from app.main.forms import BaseBankAccountForm, BaseForm
from app.pda.errors import ProviderDataApiError
from app.utils.formatting import normalize_for_search
from app.validators import (
    ValidateCompaniesHouseNumber,
    ValidateGovDateField,
    ValidatePastDate,
    ValidateVATRegistrationNumber,
)
from app.widgets import GovDateInput, GovRadioInput, GovRadioInputWithDivider, GovSubmitInput, GovTextInput

from ...fields import GovDateField, GovUKRadioField
from ..add_a_new_office import OfficeContactDetailsForm


class AddProviderForm(BaseForm):
    title = "Add a new parent provider"
    url = "add-parent-provider"

    provider_name = StringField(
        "Provider name",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m", hint="Do not include the provider type or address in the name"
        ),
        validators=[
            InputRequired(message="Enter the provider name"),
        ],
    )

    provider_type = RadioField(
        "Provider type",
        widget=GovRadioInput(
            heading_class="govuk-fieldset__legend--m",
            hint="To add an advocate or barrister, open a chambers record and use Add advocate/Add barrister.",
        ),
        validators=[InputRequired(message=("Select a provider type"))],
        choices=PARENT_FIRM_TYPE_CHOICES,
    )

    def validate_provider_name(self, field):
        if not field.data:
            return

        pda = current_app.extensions.get("pda")
        if not pda or not hasattr(pda, "provider_name_exists"):
            return

        if pda.provider_name_exists(field.data):
            raise ValidationError(f"A provider named {field.data} already exists")


class LspDetailsForm(BaseForm):
    title = "Legal services provider details"
    url = "additional-details-legal-services-provider"

    @property
    def caption(self):
        return session.get("new_provider", {}).get("firm_name", "Unknown")

    constitutional_status = RadioField(
        "Constitutional status",
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m"),
        validators=[InputRequired(message="Select the constitutional status")],
        choices=CONSTITUTIONAL_STATUS_CHOICES,
    )

    indemnity_received_date = GovDateField(
        "Indemnity received date (optional)",
        widget=GovDateInput(heading_class="govuk-fieldset__legend--m", hint="For example 27 3 2025"),
        format="%d %m %Y",
        validators=[Optional(), ValidateGovDateField(), ValidatePastDate()],
    )

    companies_house_number = StringField(
        "Companies House number (optional)",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-half",
            hint="Also known as Company Registration Number",
        ),
        validators=[ValidateCompaniesHouseNumber()],
    )


class AdvocateDetailsForm(BaseForm):
    title = "Advocate details"
    url = "advocate-details"

    @property
    def caption(self):
        return session.get("new_provider", {}).get("firm_name", "Unknown")

    solicitor_advocate = RadioField(
        "Is the provider a solicitor advocate? (optional)",
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m", classes="govuk-radios--inline"),
        choices=YES_NO_CHOICES,
        validators=[Optional()],
    )

    advocate_level = RadioField(
        "Advocate level",
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m"),
        validators=[InputRequired(message="Select the advocate level")],
        choices=ADVOCATE_LEVEL_CHOICES,
    )

    bar_council_roll_number = StringField(
        "Bar Council roll number",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-half",
        ),
        validators=[
            InputRequired("Enter the Bar Council roll number"),
            Length(max=15, message="Bar Council roll number must be 15 characters or less"),
        ],
    )


class ChambersDetailsForm(BaseForm):
    title = "Chambers details"
    url = "chambers-details"

    @property
    def caption(self):
        return session.get("new_provider", {}).get("firm_name", "unknown")

    solicitor_advocate = RadioField(
        "Is the provider a solicitor advocate?",
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m", classes="govuk-radios--inline"),
        validators=[InputRequired(message=("Select yes if the provider is a solicitor advocate"))],
        choices=YES_NO_CHOICES,
    )

    advocate_level = RadioField(
        "Advocate level",
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m"),
        validators=[InputRequired(message=("Select the advocate level"))],
        choices=ADVOCATE_LEVEL_CHOICES,
    )

    bar_council_number = StringField(
        "Bar Council roll number",
        widget=GovTextInput(heading_class="govuk-fieldset__legend--m", classes="govuk-!-width-one-half"),
        validators=[
            InputRequired(message="Enter the Bar Council roll number"),
            Length(max=15, message="Bar Council roll number must be 15 characters or less"),
        ],
    )


class HeadOfficeContactDetailsForm(OfficeContactDetailsForm):
    """This form is used both for LSP Head Office contact details and Chambers contact details as both populate the firm's head office information. They are just displayed differently to end users."""

    url = "add-contact-details"
    submit_button_text = "Continue"

    @property
    def title(self):
        if self.firm.firm_type == "Legal Services Provider":
            return "Head office contact details"
        if self.firm.firm_type == "Chambers":
            return "Add chambers contact details"

    @property
    def caption(self):
        # Get provider name from session if available
        new_provider_name = session.get("new_provider", {}).get("firm_name", "Unknown")
        return new_provider_name


class VATRegistrationForm(BaseForm):
    title = "Head office: \nVAT registration number (optional)"
    url = "add-vat-number"

    @property
    def caption(self):
        # Get provider name from session if available
        new_provider_name = session.get("new_provider", {}).get("firm_name", "Unknown")
        return new_provider_name

    vat_registration_number = StringField(
        "",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--xl",
            classes="govuk-!-width-one-half",
            hint="This is 9 numbers, sometimes with ‘GB’ at the start, for example 123456789 or GB123456789.",
        ),
        validators=[
            Optional(),
            ValidateVATRegistrationNumber(message="Enter the VAT registration number in the correct format"),
        ],
    )


class BankAccountForm(BaseBankAccountForm):
    title = "Head office: \nBank account details"
    url = "add-bank-account"

    @staticmethod
    def _digits_only(value: str | None) -> str:
        return re.sub(r"\D", "", value or "")

    @property
    def caption(self):
        # Get provider name from session if available
        new_provider_name = session.get("new_provider", {}).get("firm_name", "Unknown")
        return new_provider_name

    def validate_account_number(self, field):
        # Skip duplicate checks until format/required validators have passed.
        if self.sort_code.errors or field.errors or not self.sort_code.data or not field.data:
            return

        pda = current_app.extensions.get("pda")
        if not pda or not hasattr(pda, "get_all_bank_accounts"):
            return

        sort_code = self._digits_only(self.sort_code.data)
        account_number = self._digits_only(field.data)

        if not sort_code or not account_number:
            return

        try:
            existing_accounts = pda.get_all_bank_accounts()
        except Exception:
            # Do not block progression on transient lookup failures.
            return

        for account in existing_accounts:
            existing_sort = self._digits_only(getattr(account, "sort_code", None))
            existing_number = self._digits_only(getattr(account, "account_number", None))
            if sort_code == existing_sort and account_number == existing_number:
                raise ValidationError("This bank account already exists. Enter a different sort code or account number")

    skip_button = SubmitField(
        "Cheque payment: Skip this step", widget=GovSubmitInput(classes="govuk-button--secondary govuk-!-margin-left-2")
    )


class LiaisonManagerForm(BaseForm):
    title = "Add liaison manager"
    url = "add-liaison-manager"

    @property
    def submit_button_text(self):
        new_provider_type = session.get("new_provider", {}).get("firm_type")
        return "Submit" if new_provider_type == "Chambers" else "Continue"

    @property
    def caption(self):
        # Get provider name from session if available
        new_provider_name = session.get("new_provider", {}).get("firm_name", "Unknown")
        return new_provider_name

    first_name = StringField(
        "First name",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-third",
        ),
        validators=[
            InputRequired(message="Enter the first name"),
            Length(max=100, message="First name must be 100 characters or less"),
        ],
    )

    last_name = StringField(
        "Last name",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-third",
        ),
        validators=[
            InputRequired(message="Enter the last name"),
            Length(max=100, message="Last name must be 100 characters or less"),
        ],
    )

    email_address = StringField(
        "Email address",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-two-thirds",
        ),
        validators=[
            InputRequired(message="Enter the email address"),
            Email(message="Enter a valid email address"),
            Length(max=255, message="Email address must be 255 characters or less"),
        ],
        filters=[
            # Remove all leading and trailing whitespace from field before processing it
            lambda data: data.strip() if data else None,
        ],
    )

    telephone_number = StringField(
        "Telephone number",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-third",
        ),
        validators=[
            InputRequired(message="Enter the telephone number"),
            Length(max=20, message="Telephone number must be 20 characters or less"),
        ],
    )

    website = StringField(
        "Website (optional)",
        widget=GovTextInput(
            heading_class="govuk-fieldset__legend--m",
            classes="govuk-!-width-one-third",
        ),
        validators=[
            Optional(),
            Length(max=255, message="Website must be 255 characters or less"),
        ],
    )


class AssignContractManagerForm(BaseForm):
    title = "Assign contract manager"
    url = "assign-contract-manager"
    template = "add_provider/assign-contract-manager.html"
    success_url = "main.create_provider"
    submit_button_text = "Submit"

    search = StringField(
        "Search for a contract manager",
        widget=GovTextInput(
            form_group_classes="govuk-!-width-two-thirds",
            heading_class="govuk-fieldset__legend--s",
        ),
        validators=[Length(max=100, message="Search term must be 100 characters or less")],
    )

    contract_manager = StringField(
        "Contract manager",
        validators=[
            InputRequired(
                message="Select a contract manager, search again or skip this step if you do not know the contract manager"
            )
        ],
    )
    skip = SubmitField("Unknown: Skip this step", widget=GovSubmitInput(classes="govuk-button--secondary"))

    def __init__(self, search_term=None, page=1, selected_value=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.contract_manager_load_error = None
        try:
            self.contract_managers = self.get_contract_managers()
        except ProviderDataApiError:
            self.contract_managers = []
            self.contract_manager_load_error = "Unable to load contract managers with the configured backend"

        # Set search field data
        self.search_term = search_term
        if search_term:
            self.search.data = search_term

        # Filter contract managers based on search term
        filtered_managers = self.contract_managers
        if self.search_term:
            search_lower = normalize_for_search(self.search_term)
            filtered_managers = [
                manager
                for manager in self.contract_managers
                if search_lower in normalize_for_search(self.get_contract_manager_name(manager))
            ]

        self.page = page
        self.contract_managers_shown_per_page = 10
        self.num_results = len(filtered_managers)

        # Limit results and populate choices
        start_id = self.contract_managers_shown_per_page * (self.page - 1)
        end_id = self.contract_managers_shown_per_page * (self.page - 1) + self.contract_managers_shown_per_page

        filtered_managers = filtered_managers[start_id:end_id]
        manager_rows = [
            {"guid": self.get_contract_manager_guid(manager), "name": self.get_contract_manager_name(manager)}
            for manager in filtered_managers
            if self.get_contract_manager_guid(manager)
        ]

        # Create RadioDataTable for contract managers
        table_structure: list[TableStructureItem] = [
            {"text": "Name", "id": "name", "classes": "govuk-!-width-full"},
        ]
        self.contract_manager_table = RadioDataTable(
            structure=table_structure,
            data=manager_rows,
            radio_field_name="contract_manager",
            radio_value_key="guid",
        )

        # Store selected value for table rendering
        self.selected_value = selected_value

    def get_contract_managers(self):
        pda = current_app.extensions["pda"]
        return pda.get_list_of_contract_manager_names()

    @staticmethod
    def get_contract_manager_guid(manager):
        if isinstance(manager, dict):
            return manager.get("guid")
        return getattr(manager, "guid", None)

    @staticmethod
    def get_contract_manager_name(manager):
        if isinstance(manager, dict):
            return manager.get("name") or manager.get("contractManagerId") or "Unknown contract manager"
        return (
            getattr(manager, "display_name", None)
            or getattr(manager, "contract_manager_id", None)
            or "Unknown contract manager"
        )

    def find_contract_manager_by_name(self, name: str | None):
        if not name:
            return None
        target = normalize_for_search(name)
        return next(
            (
                manager
                for manager in self.contract_managers
                if normalize_for_search(self.get_contract_manager_name(manager)) == target
            ),
            None,
        )

    def get_contract_manager_by_guid(self, guid: str | None):
        if not guid:
            return None
        return next(
            (manager for manager in self.contract_managers if self.get_contract_manager_guid(manager) == guid), None
        )


class AddBarristerDetailsForm(BaseForm):
    title = "Barrister details"
    url = "provider/<firm:firm>/add-barrister"
    submit_button_text = "Continue"

    def __init__(self, firm=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.firm = firm

    @property
    def caption(self):
        if self.firm:
            return self.firm.firm_name
        return "Unknown chambers"

    barrister_name = StringField(
        "Barrister name",
        widget=GovTextInput(heading_class="govuk-fieldset__legend--s", classes="govuk-!-width-one-half"),
        validators=[
            InputRequired(message="Enter the barrister name"),
            Length(max=255, message="Barrister name must be 255 characters or less"),
        ],
    )

    barrister_level = GovUKRadioField(
        "Barrister level",
        widget=GovRadioInputWithDivider(heading_class="govuk-fieldset__legend--s"),
        choices=ADVOCATE_LEVEL_CHOICES,
        validators=[InputRequired(message="Select the barrister level")],
    )

    bar_council_roll_number = StringField(
        "Bar Council roll number",
        widget=GovTextInput(heading_class="govuk-fieldset__legend--s", classes="govuk-!-width-one-half"),
        validators=[
            InputRequired(message="Enter the Bar Council roll number"),
            Length(max=15, message="Bar Council roll number must be 15 characters or less"),
        ],
    )


class AddAdvocateBarristerCheckForm(BaseForm):
    template = "add_provider/barrister-check-form.html"
    same_liaison_manager_as_chambers = RadioField(
        label="Do you want to use the same liaison manager as the chambers?",
        choices=YES_NO_CHOICES,
        widget=GovRadioInput(heading_class="govuk-fieldset__legend--m"),
        validators=[InputRequired(message="Select yes if you want to use the same liaison manager as the chambers")],
    )

    @property
    def title(self):
        if self.model_type.lower() == "barrister":
            return "Barrister details"
        else:
            return "Advocate details"

    @classmethod
    def url(cls, model_type):
        if model_type.lower() == "barrister":
            return "provider/<firm:firm>/barrister-liaison-manager-check"
        else:
            return "provider/<firm:firm>/advocate-liaison-manager-check"

    @property
    def caption(self):
        if self.model_type.lower() == "barrister":
            return session["new_barrister"]["barrister_name"]
        else:
            return session["new_advocate"]["advocate_name"]
        return self.firm.firm_name

    def __init__(self, firm, model_type: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.firm = firm
        self.model_type = model_type


class AddAdvocateBarristerLiaisonManagerForm(LiaisonManagerForm):
    @classmethod
    def url(cls, model_type):
        if model_type.lower() == "barrister":
            return "provider/<firm:firm>/add-barrister-liaison-manager"
        else:
            return "provider/<firm:firm>/add-advocate-liaison-manager"

    @property
    def caption(self):
        if self.model_type.lower() == "barrister":
            return session["new_barrister"]["barrister_name"]
        else:
            return session["new_advocate"]["advocate_name"]

    def __init__(self, firm, model_type, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.firm = firm
        self.model_type = model_type


class AddAdvocateDetailsForm(BaseForm):
    title = "Advocate details"
    url = "provider/<firm:firm>/add-advocate"
    submit_button_text = "Continue"

    def __init__(self, firm=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.firm = firm

    @property
    def caption(self):
        if self.firm:
            return self.firm.firm_name
        return "Unknown chambers"

    advocate_name = StringField(
        "Advocate name",
        widget=GovTextInput(heading_class="govuk-fieldset__legend--s", classes="govuk-!-width-one-half"),
        validators=[
            InputRequired(message="Enter the advocate name"),
            Length(max=255, message="Advocate name must be 255 characters or less"),
        ],
    )

    advocate_level = RadioField(
        "Advocate level",
        widget=GovRadioInputWithDivider(heading_class="govuk-fieldset__legend--s"),
        choices=ADVOCATE_LEVEL_CHOICES,
        validators=[InputRequired(message="Select the advocate level")],
    )

    sra_roll_number = StringField(
        "Solicitors Regulation Authority roll number",
        widget=GovTextInput(heading_class="govuk-fieldset__legend--s", classes="govuk-!-width-one-half"),
        validators=[
            InputRequired(message="Enter the Solicitors Regulation Authority roll number"),
            Length(max=15, message="Solicitors Regulation Authority roll number must be 15 characters or less"),
        ],
    )
