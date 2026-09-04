import BasePage from './BasePage.js';
class LegalServiceProviderDetailsPage extends BasePage {
    constructor(page) {
        super(page);
        this.constitutionalStatusRadioButton = this.page.getByRole('radio');

    }
    async selectConstitutionalStatus() {
       const numberOfRadioButtons = await this.constitutionalStatusRadioButton.count();
       const randomIndex = Math.floor(Math.random() * numberOfRadioButtons);
       this.constitutionalStatusRadioButton = this.constitutionalStatusRadioButton.nth(randomIndex);
       await this.constitutionalStatusRadioButton.scrollIntoViewIfNeeded();
        await this.constitutionalStatusRadioButton.check();
        await this.continueButton.click();
    }

}
export default LegalServiceProviderDetailsPage;