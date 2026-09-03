import BasePage from './BasePage.js';
class HeadOfficeContactDetailsPage extends BasePage {
    constructor(page) {
        super(page);

        this.addressLine1TextBox = page.locator('#address_line_1');
        this.townTextBox = page.locator('#city');
        this.postCodeTextBox = page.locator('#postcode');
    }

    async fillMandatoryFieldsForHeadOfficeContactDetails(addressLine1, town, postCode) {
        await this.addressLine1TextBox.fill(addressLine1);
        await this.townTextBox.fill(town);
        await this.postCodeTextBox.fill(postCode);
        await this.continueButton.click();
    }
}
export default HeadOfficeContactDetailsPage;