# Roblox Face Animation Exporter for Blender

A Blender add-on for exporting facial image sequence animations into **Moon Animator 2** save files for Roblox.

> **Note**: This add-on is designed specifically to work with a specific face rig. You can download/view the compatible rig here: **[Download Compatible Rig](https://link-to-rig.com)**.

## Installation

1. **Blender Add-on**: Download `faceanim_exporter.zip` from the [Releases](https://github.com/mr-xen0/rbx-faceanim-exporter/releases) page.
2. **Roblox Plugin**: Install the plugin in Roblox Studio from the [Roblox Creator Store](https://create.roblox.com/store/asset/...).
3. Enable the add-on in Blender preferences (see **Blender Setup** below).

## Blender Setup

1. Open Blender and go to **Edit > Preferences > Add-ons**.
2. Click **Install...** (or **Install from Disk**) and select `faceanim_exporter.zip`.
3. Enable the **Face Animation Exporter** add-on.
4. In the 3D Viewport, open the Sidebar by pressing `N`, then click the **RBX Face Animation** tab.

## Usage

### Basic Workflow

#### 1. In Blender
- Select your target rig in the **RBX Face Animation** sidebar tab.
- If you duplicated your rig, click **Auto Fix Duplicated Rig** to handle shared materials and retarget drivers.
- Select the animation channels you want to export.
- Click **Copy JSON** (to copy animation data to clipboard) or **Export to File** (to save a `.json` file).

#### 2. In Roblox Studio
- Open the **Face Animation Importer** plugin.
- Click **Generate face setup**.
- Select the created face setup under **Target face rig in scene**.
- Import your animation using **Import Animation from Clipboard** or **Import Animation from File**.
- Make sure you select all the animation channels you want to import under **Animation channels**.
- Select your Moon 2 file under **Moon Animator 2 files** to which you want to add the animation.
- Press **Add face animation to Moon file**.

## Features

- **Multi-Rig Support**: Easily handle duplicated or cloned rigs by separating shared materials and retargeting drivers.
- **Flexible Export**: Export animation data directly to your clipboard or save as a `.json` file.
- **Channel Selection**: Select specific facial animation channels to include in your export.

## Configuration

### Blender Properties
- **Target Rig**: Specifies the active armature/rig object.
- **Rig ID**: Unique identifier assigned to the rig.
- **Animation ID**: Identifier used when generating export filenames.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/mr-xen0/rbx-faceanim-exporter/issues).
