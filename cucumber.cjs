module.exports = {
  default: {
    paths: ['e2e/features/**/*.feature'],
    import: ['e2e/support/**/*.js', 'e2e/steps/**/*.js'],
    format: ['progress', 'html:e2e/test-results/cucumber-report.html'],
    publishQuiet: true,
  },
};