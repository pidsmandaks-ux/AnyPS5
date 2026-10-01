# Compatibility diagnostics

AnyPS5 can record compatibility failures without changing normal runtime behavior. This is intended for bringing up additional titles and collecting reproducible information for generic fixes.

Enable diagnostics with:

```
ANYPS5_DIAGNOSTICS=1
```

To also persist the diagnostic stream to a file:

```
ANYPS5_DIAGNOSTICS=1
ANYPS5_DIAGNOSTICS_FILE=compatibility.log
```

Set `ANYPS5_DIAGNOSTICS_ALL=1` to keep repeated identical events instead of suppressing duplicate messages.

The diagnostic stream currently records:
- unimplemented PRX exports, including the function name;
- AGC graphics validation failures;
- missing Vulkan device functions;
- Vulkan result failures detected by the graphics context;
- unavailable Vulkan memory-type selections.

Example:

```
[AnyPS5][diagnostic] 1790000000.123 tid=... category=prx name=sceExampleFunction detail=function is not implemented
[AnyPS5][diagnostic] 1790000001.456 tid=... category=agc.graphics name=require detail=unsupported shader execution mode
```

The exception text and normal program behavior are unchanged. Diagnostics are emitted only when `ANYPS5_DIAGNOSTICS` is enabled.

For a new game, keep the diagnostic file from the earliest failure through the point where the title stops. Missing PRX functions, graphics validation reasons, and repeated Vulkan failures can then be grouped into a generic compatibility change rather than a title-specific workaround.
