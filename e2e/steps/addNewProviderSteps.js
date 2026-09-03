import { Given, When, Then } from "@cucumber/cucumber";
import POManager from "../pages/POManager.js";
import { faker } from '@faker-js/faker';

Given('User is on the add provider screen', async function () {
    const pageObject = new POManager(this.page);
    await this.page.goto("/providers");
    await pageObject.getProviderRecordsPage().clickNewProviderButton();
    await pageObject.getAddNewParentProviderPage().validatePageHeading();

});

When('User fills all mandatory fields for LSP provider type', async function () {

    const providerName = `Test Provider ${faker.string.alphanumeric(6)}`;
    const officeAddress = faker.location.streetAddress();
    const town = faker.location.city();
    const postcode = 'LS1 2RD'; // faker's UK postcodes aren't always in valid GOV.UK format, keep fixed or validate
    const vatNumber = `GB${faker.string.numeric(9)}`;
    const accountName = `Test Bank Account ${faker.string.alphanumeric(4)}`;
    const sortCode = faker.finance.creditCardCVV().padEnd(6, '0').slice(0, 6); // 6-digit sort code
    const accountNumber = faker.finance.accountNumber(8);
    const firstName = faker.person.firstName();
    const lastName = faker.person.lastName();
    const email = faker.internet.email({ firstName, lastName });
    const phone = `07${faker.string.numeric(9)}`;

    const pageObject = new POManager(this.page);

    await pageObject.getAddNewParentProviderPage().fillMandatoryFieldsForLSPProvider(providerName);
    await pageObject.getLegalServiceProviderDetailsPage().selectConstitutionalStatus();
    await pageObject.getHeadOfficeContactDetailsPage().fillMandatoryFieldsForHeadOfficeContactDetails(officeAddress, town, postcode);
    await pageObject.getHeadOfficVatRegPage().fillMandatoryFieldsForHeadOfficeVatReg(vatNumber);
    await pageObject.getHeadOfficeBankDetailsPage().fillMandatoryFieldsForHeadOfficeBankDetails(accountName, sortCode, accountNumber);
    await pageObject.getLiaisonManagerPage().fillMandatoryFieldsForLiaisonManager(firstName, lastName, email, phone);
    await pageObject.getAssigneContractManagerPage().selectContractManagerOption();
});

Then('User should be able to save the new provider record successfully', async function () {
    const pageObject = new POManager(this.page);
    await pageObject.getProviderSuccessPage().verifySuccessMessage();

});