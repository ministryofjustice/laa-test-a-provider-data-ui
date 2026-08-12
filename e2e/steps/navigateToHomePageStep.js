
    const { Given, When, Then } = require('@cucumber/cucumber');
    const { expect } = require('@playwright/test');
    
    Given('I am on the home page', async function() {
        await this.page.goto("/");
        await expect(this.page).toHaveTitle("Manage a provider's data – GOV.UK");
    });

    When('I select the sign in button', async function() {
        await this.page.getByRole('button', { name: 'Sign in' }).click();
    });

    Then('I am taken to the provider records screen', async function() {
        await this.page.getByRole('heading', { name: 'Provider records' }).isVisible();
    }); 
