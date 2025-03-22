# XplainCrypto Logs

This directory contains log files for the XplainCrypto application.

## Log Files

- **xplaincrypto.log**: Main application log file
- **xplaincrypto.log.1, xplaincrypto.log.2, etc.**: Rotated log files when the main log grows beyond 10MB

## Log Format

The log format is:

```
YYYY-MM-DD HH:MM:SS,SSS - ModuleName - Level - Message
```

Example:
```
2025-03-22 16:13:26,035 - XplainCrypto - INFO - Main module loaded successfully
```

## Log Levels

The logs include entries with the following severity levels (from least to most severe):

- **DEBUG**: Detailed information, typically useful only when diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, but the application is still working
- **ERROR**: Due to a more serious problem, the application has not been able to perform a function
- **CRITICAL**: A very serious error, indicating that the application itself may be unable to continue running

## Troubleshooting

When investigating issues, look for ERROR or WARNING level messages that may indicate the source of the problem.

If debugging a specific research project, search for the project name in the logs to track the full lifecycle of the research process.

For performance analysis, look for timestamps between consecutive operations to identify bottlenecks in the process.

## Log Rotation

Logs are automatically rotated when they reach 10MB in size, and up to 5 backup files are kept. This prevents the logs from consuming too much disk space. 