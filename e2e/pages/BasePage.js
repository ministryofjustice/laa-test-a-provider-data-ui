class BasePage {
    constructor(page) {
        this.page = page;
        this.continueButton = this.page.getByRole('button', { name: 'Continue' });
    
    }

    async clickContinueButton() {
        await this.continueButton.click();
    }
}
export default BasePage;