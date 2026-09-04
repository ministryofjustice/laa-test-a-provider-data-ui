import { Before, After, setDefaultTimeout } from '@cucumber/cucumber';

setDefaultTimeout(30_000);

Before(async function () {
  await this.openBrowser();
});

After(async function (scenario) {
  if (scenario.result?.status === 'FAILED') {
      if (this.page) {
        await this.page.screenshot({
          path: `test-results/screenshots/${Date.now()}.png`,
          fullPage: true,
        });
      }
  }

  // Closing the context saves the video file.
  await this.page?.close();
  await this.context?.close();
  await this.browser?.close();
});