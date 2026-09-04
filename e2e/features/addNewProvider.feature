@wip
Feature: User can add new parent provider for both LSP and Chamber types

From the provider records screen, user can select the add new parent provider and proceed to 
next screens and fills all mandatory fields

Scenario: User adds new provider- LSP

Given User is on the add provider screen
When User fills all mandatory fields for LSP provider type
Then User should be able to save the new provider record successfully