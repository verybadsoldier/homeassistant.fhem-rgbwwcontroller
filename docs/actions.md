# FHEM RGBWW Controller - Actions Reference

The FHEM RGBWW Controller integration provides several powerful custom actions to control your LED strips. Besides the standard Home Assistant light actions (like turning the light on or off), you can leverage these custom actions to orchestrate complex animations and precisely control the hardware playback queue.

---

## 1. Animation Actions (YAML List)

These actions allow you to define animation sequences using structured YAML lists. This is perfect for building complex automations via the Home Assistant UI or when you prefer structured data over CLI commands.

* **`fhem_rgbwwcontroller.animation_hsv`**: Run an animation targeting the HSV (Hue, Saturation, Value) and Color Temperature channels.
* **`fhem_rgbwwcontroller.animation_rgbww`**: Run an animation targeting the raw hardware channels (Red, Green, Blue, Cold White, Warm White).

### Payload Parameters (`anim_definitions`)

Both actions accept a list of animation steps under the `anim_definitions` key. Each step can contain the following parameters:

#### Color/Target Values
* **HSV Mode**: `hue` (0-360), `saturation` (0-100), `brightness` (0-100), `color_temp_kelvin`.
* **RGBWW Mode**: `red`, `green`, `blue`, `cw`, `ww` (Raw PWM values, typically 0-1023).

#### Transition & Timing
* **`transition_mode`**: Defines how the transition value is interpreted.
    * `time`: The transition duration.
    * `speed`: The rate of change.
* **`transition_value`**: 
    * If mode is `time`: The fade duration in **milliseconds** (ms).
    * If mode is `speed`: Degrees per minute (for hue) or percentage points per minute (for other channels).
* **`stay`**: How long the controller holds this color before moving to the next step, defined in **milliseconds** (ms).

#### Execution Control
* **`requeue`** (boolean): If `true`, this individual animation step will be pushed to the back of the queue once it finishes, creating a loop for this specific step.
* **`anim_name`** (string): Assigns a custom name to this step (useful for tracking hardware events).

#### Queue Policy (`queue_policy`)
This parameter dictates how the hardware scheduler handles this step relative to currently playing animations.

| Policy | Behavior |
| :--- | :--- |
| **`single` (Default)** | Clears the entire queue and plays this animation exclusively. |
| **`front_reset`** | Puts the animation at the front of the queue. Once it finishes, the originally running animation will restart from its beginning. |
| **`front`** | Puts the animation at the front of the queue. The currently running animation is interrupted, but will continue exactly from where it left off once this new animation finishes. |
| **`back`** | Appends the animation to the end of the current queue. It will play after all previously queued animations finish. |

### Example (YAML List)
```yaml
action: fhem_rgbwwcontroller.animation_hsv
target:
  entity_id: light.my_led_strip
data:
  anim_definitions:
    - hue: 0
      saturation: 100
      brightness: 100
      transition_mode: time
      transition_value: 2000
      stay: 5000
    - hue: 120
      saturation: 100
      transition_mode: time
      transition_value: 2000
      stay: 5000
      queue_policy: back
      requeue: true
```

---

## 2. Playback Control (`control_channel`)

The `control_channel` action allows you to actively intervene in the hardware playback state of specific channels without sending new colors.

* **Action**: `fhem_rgbwwcontroller.control_channel`

### Parameters
* **`command`** (string): The action to perform.
    * `pause`: Freezes the current transition on the selected channels.
    * `continue`: Resumes a paused transition.
    * `stop`: Stops the transition immediately and clears the queue for the selected channels.
* **`channels`** (list of strings): The specific channels to apply the command to.
    * Options: `hue`, `saturation`, `value`, `color_temp`

### Example
Pause the color transition (hue and saturation) but let brightness changes continue:
```yaml
action: fhem_rgbwwcontroller.control_channel
target:
  entity_id: light.my_led_strip
data:
  command: "pause"
  channels:
    - "hue"
    - "saturation"
```

---

## 3. Animation Actions (CLI Interface)

For advanced users who prefer compact string definitions over YAML lists, the integration provides parallel CLI actions. This syntax allows you to define complex lighting animations, relative shifts, loops, and overrides using a single string.

* **`fhem_rgbwwcontroller.animation_cli_hsv`**
* **`fhem_rgbwwcontroller.animation_cli_rgbww`**

### CLI Command Syntax

A CLI command string consists of one or more **steps**, separated by a semicolon (`;`). 

**Structure of a single step:**
`[Color] [Transition] [StayTime] [Flags]`

*(Parameters are separated by spaces. You can omit values to keep their current state).*

#### A. Color Definition (Absolute or Relative)
Values are separated by commas. You can provide absolute target values, or you can use **relative values** by adding a `+` or `-` prefix to shift the current state up or down.

* **HSV Mode**: `H,S,V,CT`
    * *Absolute Example*: `120,100,50` (Green, 100% saturation, 50% brightness)
    * *Relative Example*: `+20,,-10` (Increase Hue by 20 degrees, keep Saturation the same, decrease Brightness by 10%)
* **RGBWW Mode**: `R,G,B,CW,WW`
    * *Relative Example*: `+50,+50,+