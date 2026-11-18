# zFAM
z/OS-based File Access Manager

zFAM is a cloud enabled distributed NoSQL key/value store (KVS) file system in the z/OS environment. Very high performing and highly available system used to store text or binary content. Single instances can be shared by multiple clients or unique instances can be defined for each individual client. 

- L2 Distributed write thru cache to persistent disk
- Key/Value structure
  - Key can be from 1 to 255 bytes
  - Key cannot contain embedded spaces.
  - Key names are case sensitive, "Rangers" is different than "rangers".
  - Value can be from 1 byte to 3.2 Megabytes; with the `zFAM-LOB` and `zFAM-Append` headers a binary value can grow up to 2GB per key (see [Usage.md](./Usage.md)).
  - Both text and binary data values are accepted.
- HTTP/HTTPS transmission depending on if data is needing to be secured in transit
- Transactional based system (geared for high volume I/O)
- Basic authentication access (RACF security) for CRUD operations
- ACID compliant (Atomic, Consistent, Isolation, Durable)
- RESTful service supporting:
  - GET:    Retrieve key/value
  - POST:   Adds key/value pair to instance, fails with 409 on duplicate entries
  - PUT:    Updates key/value pair in instance, fails with 204 when key is not found
  - DELETE: Delete a key/value from the instance
- Built-in expiration process.
- Multiple modes of operation:
  - Basic Mode: Simple key/value pair
  - Query/zQL Mode: Functions a little like a DBMS with SELECT/INSERT/UPDATE commands.
- Six Sigma Availablility:
  - Active/Single (High Availability at a single data center)
  - Active/Standby (High Availability across multiple data centers)
  - Active/Active (Continuous Availability across multiple data centers)
  
As part of the product there is a built-in expiration process that runs automatically in the background. Refer to the installation instructions on setting up zFAM instances. Expiration process continually scans the zFAM data looking for keys that have expired and removes them. There are no additional web service calls required to initiate or trigger this component. Each key has its own time to live (`ttl`, in days): the default is 2555 days (7 years) and the maximum is 36500 days.

Note: The keys are actually stored in an indexed VSAM file so the keys are stored in sorted ascending order. This allows for the special features to query multiple keys and values in ascending or descending order.

## About this project 

Please refer to the following locations for additional info regarding this project:

- [System Requirements and Considerations.md](./System%20Requirements%20and%20Considerations.md) for minimum software version requirements and key environment configuration considerations
- [Installation.md](./Installation.md) for instructions on installing and setting up this service
- [Usage.md](./Usage.md) for API descriptions, sample code snippets for consuming the service, other usage related details
- [docs/architecture.md](./docs/architecture.md) for how the programs, CICS resources and VSAM data sets fit together, with a [diagram](./docs/diagrams/architecture.png)
- [example_basic_mode.md](./example_basic_mode.md) and [example_query_mode.md](./example_query_mode.md) for worked examples
- [howto_define_query_mode.md](./howto_define_query_mode.md) and [howto_define_security.md](./howto_define_security.md) for defining Query Mode fields and security
- [http_response_codes.md](./http_response_codes.md) for the HTTP status codes zFAM returns

### Repository layout

| Path | Contents |
|---|---|
| `Source/` | COBOL (`.cbl`) and HLASM (`.asm`) programs, copybooks (`.cpy`) and macros (`.mac`), CSD definitions (`.rdo`), IDCAMS definitions (`.idcams`), document templates (`FA##FD`, `FA##SD`, `FA##DC`), `CONFIG.txt` and the `REXXREPL` substitution exec |
| `JCL/` | Jobs to customize the source (`CONFIG`), build (`ASMZFAM`), define CSD groups (`CSDZFAM*`), define an instance (`DEFFA##`, `DEFCI`, `DEFEXPR`) and its templates (`FA##FD`, `FA##SD`, `FA##DC`) |
| `docs/` | Architecture description and diagram (`docs/diagrams/architecture.dot`, rendered to PNG and SVG) |

### Contributors

- **_Randy Frerking_**,	Walmart Technology
- **_Rich Jackson_**, Walmart Technology
- **_Michael Karagines_**, Walmart Technology
- **_Trey Vanderpool_**, Walmart Technology
