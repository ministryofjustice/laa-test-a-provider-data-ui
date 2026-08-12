@test
Feature: navigate to home page

Scenario: Navigate to home page
Given I am on the home page
When I select the sign in button
Then I am taken to the provider records screen
