## R CMD check results

0 errors, 0 warnings, 1 notes

This is a new release.

## Resubmission

> If there are references describing the methods in your package, please add
> these in the description field of your DESCRIPTION file in the form authors
> (year) <doi:...> authors (year, ISBN:...) or if those are not available:
> <https:...> with no space after 'doi:', 'https:' and angle brackets for
> auto-linking.

The package retrieves and verifies registered datasets and does not implement
statistical methods, so I do not think that there are any relevant references to
add to the DESCRIPTION.

> Please add small executable examples in your Rd-files to illustrate the use of
> the exported function but also enable automatic testing.

I've added executable examples for inspecting dataset metadata and citations,
selecting a registry, and managing a temporary cache.
