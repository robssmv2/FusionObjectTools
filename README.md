# Fusion Object Tools

Windows tools for Autodesk Fusion, published as the **ObjectTypeInspector**
Python add-in. No separate Python installation or administrator access is
needed to use the add-in.

## Features

- **Object Type Inspector:** dockable palette identifying API-visible solid,
  surface, mesh, sheet-metal, and Form/T-Spline bodies.
- **Dissolve All:** dissolves eligible non-parametric B-Rep features across the
  active design's local components while retaining B-Rep geometry.
- **Optional Base Features:** an unchecked-by-default option includes eligible
  non-parametric Base Features. Forms, parametric features, and linked external
  components stay protected.

**Save a separate design copy before dissolving.** Dissolve removes editable
feature information. It does not simply hide browser entries.

## Install or update (Windows)

1. Download `FusionObjectTools-1.0.0-Windows.zip` from the repository's
   **Releases** page. Extract the entire ZIP to a folder.
2. Close Autodesk Fusion.
3. Open Windows PowerShell in the extracted folder and run:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1
   ```

   This execution-policy setting applies only to this PowerShell process. It
   does not change your system policy. Inspect the script before running it.
   Managed company policies may still block unsigned scripts; use the manual
   installation below instead of changing organizational security settings.

4. Open Fusion and press **Shift+S**. On the **Add-Ins** tab select
   **ObjectTypeInspector**, click **Run**, and enable **Run on Startup**.
5. Find **Dissolve All** under **Design > Solid > Modify**.

The installer copies only the add-in's runtime files into:

```text
%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\ObjectTypeInspector
```

When updating, it moves the previous installation into
`%APPDATA%\FusionObjectTools\Backups` before installing the new version.
Other add-ins are not modified. An existing installation is restored if the
final installation move fails.

### Manual installation

With Fusion closed, copy the extracted `ObjectTypeInspector` folder into
`%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`. Back up any existing folder
with that name first. If the add-in is not listed in Fusion, use the add-in
manager's **+ / Add** control to select that folder.

### Uninstall or restore

Close Fusion and remove only the installed `ObjectTypeInspector` folder.
To restore a previous version, copy its backed-up folder back into `AddIns`
under the name `ObjectTypeInspector`. Existing backups are not deleted.

## Find in Browser hotkey (native Fusion setting)

This is a Fusion setting, not a feature installed by this add-in:

1. Open **Text Commands** with **Ctrl+Alt+C**, and select **Txt** input mode.
2. Enter `hotkey.dialog FindInBrowser`.
3. Assign an unused shortcut. Select an object in the canvas and press it to
   locate the object in the browser tree.

This setup was confirmed in the original user's Fusion installation. Hidden
command availability may change between Fusion versions. No Collapse All
shortcut or command is included.

## Known limitations

Some component-level T-Spline selections are not returned by Fusion's public
selection API. An empty selection displays **Possible Form / T-Spline** as a
guess, not a confirmed type; blank-space clicks and Escape have the same result.
Plastic material identification is a material-name heuristic, not a geometry
type or composition guarantee.

See [the add-in documentation](ObjectTypeInspector/README.md) for classification,
diagnostic, and dissolve behavior details.

## Development

Python is needed for mocked regression tests, but not for installation:

```powershell
python -B -m unittest discover -s .\ObjectTypeInspector\tests -v
```

Build the runtime ZIP and its SHA-256 checksum:

```powershell
powershell.exe -NoProfile -File .\Build.ps1
```

Output is written to `dist`. The ZIP excludes tests, caches, and developer files.
Mocked tests do not replace live Fusion testing. The original user confirmed
the standard and optional Base Feature dissolve paths worked in their model.
