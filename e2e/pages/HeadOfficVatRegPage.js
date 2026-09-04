import BasePage from './BasePage.js';
class HeadOfficVatRegPage extends BasePage {
    constructor(page) {
        super(page);
        this.vatRegNumberInput = this.page.locator('#vat_registration_number');
    }

    async fillMandatoryFieldsForHeadOfficeVatReg(vatRegNumber) {
        await this.vatRegNumberInput.fill(vatRegNumber);
        await this.continueButton.click();
    }
}
export default HeadOfficVatRegPage;