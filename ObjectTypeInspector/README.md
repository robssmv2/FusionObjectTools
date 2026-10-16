# Object Type Inspector

This Fusion 360 Python add-in watches the normal canvas selection and displays
the selected body's type in a dockable palette. Its manifest enables **Run on
Startup**, so after Fusion loads it continues monitoring selections in the
background until stopped from **Utilities > Add-Ins > Scripts and Add-Ins**.

After updating the add-in, select it in **Scripts and Add-Ins**, click **Stop**,
then **Run** to reload the Python code and palette. No Fusion restart is needed.
The palette uses an encoded file URL so Windows paths containing spaces load
correctly in Fusion's embedded browser.

The palette distinguishes solid B-Rep bodies, surface B-Rep bodies, mesh bodies,
T-Spline/Form bodies, and sheet-metal B-Rep bodies. Selecting a face, edge, or
vertex reports the body it belongs to; selecting a component lists its bodies.
For a selected component or occurrence, the list includes B-Rep and mesh bodies
plus T-Spline bodies retrieved from that component's Form features. A finished
Form can therefore appear alongside its resulting B-Rep body in this component
summary. The summary covers bodies owned directly by the selected component,
not bodies in nested child components.
Selecting a Form feature lists its T-Spline bodies. A body produced by **Finish
Form** is a B-Rep solid or surface; its current geometry type is reported, not
its modeling history.

Fusion's `activeSelectionChanged` event only covers the default Select command,
not selections inside other commands. If a click does not update the inspector,
use **Refresh selection** to read Fusion's exposed active selection directly.
Expand **Selection diagnostics** to see the active command, the number of
API-visible selections, and their API types. A zero count means Fusion exposed
no selected entity to inspect; it does not establish that an object is a Form.
For selected components, diagnostics also include body counts, Form feature
body counts, feature API types, and child-component inventories. These are
read-only model queries; they do not activate components or edit Form features.
In particular, clicking a T-Spline/Form object may leave the API selection
empty even when Fusion highlights it. Automatic click-based classification
cannot cover those selections. Recognizing a `TSplineBody` supplied by the API
is not a guarantee that Fusion exposes it through canvas selection.

For empty API selections, the palette displays **Possible Form / T-Spline**
as an explicitly unconfirmed hint. It also warns that blank-space clicks,
Escape, and cleared selections can produce the same result. This hint does not
change the classification of any API-visible object.

Fusion exposes a material name for an assigned body material, but not a
general-purpose plastic category on that material. The inspector marks a
material as plastic when its name contains a recognized polymer/material term
(for example ABS, nylon, or polycarbonate); this is a name-based hint, not a
guarantee about the material's composition.

## Dissolve All

After restarting the add-in, open **Design > Solid > Modify > Dissolve All**.
The command inventories the entire active design, including nested local
components, and displays a confirmation with the number of eligible features.
Cancel leaves the model unchanged. Save a separate copy before confirming.

This uses `Feature.dissolve()`, not deletion: editable non-parametric feature
information is removed while its B-Rep geometry remains. Each component
definition is processed once even when it has multiple occurrences. Features
are processed in reverse collection order.

The **Include Base Features (B-Rep)** checkbox is off by default. Enable it to
also dissolve eligible non-parametric base features that have B-Rep bodies.
This removes their editable source grouping as well. The confirmation shows
eligible counts with and without base features; execution rechecks eligibility
using the chosen option.

Parametric features, Form features, and features without B-Rep bodies are always
skipped. Base features are skipped unless the checkbox is enabled.
Linked external component subtrees are excluded; edit
their source designs separately. The command does not switch design history
off, delete construction geometry, or dissolve component occurrences. Thus,
some browser entries intentionally remain.

The results dialog reports dissolved, invalidated, and skipped feature counts,
plus excluded linked occurrences. An API failure stops processing and marks
the Fusion command transaction as failed so Fusion can abort it. Errors are
reported rather than silently continuing. Geometry preservation and Undo
behavior must still be verified inside Fusion on a saved copy.

Mocked API regression tests can be run with:

```powershell
python -B -m unittest discover -s .\ObjectTypeInspector\tests -v
```
