 class ProviderRecordsPage {
    constructor(page) {
        this.page = page;
        this.addNewProviderButton = this.page.getByRole('button', { name: 'Add a new parent provider' });
        this.searchBox = this.page.locator('#search');
        this.searchBoxButton = this.page.getByRole('button', { name: 'Search' });

    }


    async searchProvider(providerName) {
        await this.searchBox.fill(providerName);
        await this.searchBoxButton.click();
    }

    async clickNewProviderButton() {
        await this.addNewProviderButton.click();
    }
 }
 export default ProviderRecordsPage;