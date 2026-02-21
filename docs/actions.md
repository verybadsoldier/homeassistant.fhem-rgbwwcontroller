# FHEM RGBWW Controller - Advanced Actions Reference

The FHEM RGBWW Controller integration provides several powerful custom actions to control your LED strips. Besides the standard Home Assistant light actions (like simply turning the light on or off), you can leverage these custom actions to orchestrate complex animations, loops, and precisely control the hardware playback queue.

**💡 UI Support:** You do not need to write raw YAML to use these features! All actions are fully integrated into the Home Assistant UI. You can configure them comfortably using dropdowns and input fields in the Automation Editor or via **Developer Tools -> Actions**.

---

## 1. Core Concepts (How the Hardware Works)

Regardless of whether you use the structured YAML actions or the compact CLI syntax, they all control the same underlying hardware features. Understanding these concepts is key to building great animations.

### A. Color Models & Targeting
* **HSV + CT Mode:** Targets Hue (0-360), Saturation (0-100), Brightness/Value (0-100), and Color Temperature.
* **RGBWW Mode:** Targets the raw physical hardware channels directly: Red, Green, Blue, Cold White, Warm White (Raw PWM values, typically 0-1023).
* **Relative vs. Absolute:** You can send exact target values (e.g., "Set Brightness to 50%"), or **relative values** (e.g., "Increase Brightness by 10%"). Relative shifts are incredibly powerful for creating endless, shifting loops.

### B. Transitions & Timing
* **Time (Duration):** The transition takes a fixed amount of time (e.g., fade over 5 seconds).
* **Speed:** The transition runs at a fixed speed (e.g., change Hue at 200 degrees per minute).
* **Stay Time:** The time the controller holds the color *after* the transition completes before moving to the next animation step. 

### C. The Hardware Queue (Crucial for Animations)
When you send an animation step to the controller, you must tell the hardware scheduler *where* to put it. 

* **Queue Policies (Where to put the step):**
  * **Single (Default):** Clears the entire current playback queue and plays this step immediately.
  * **Back:** Appends the step to the end of the current queue. It waits its turn.
  * **Front:** Injects the step at the front. The currently running animation pauses, plays your new step, and then resumes exactly where it left off.
  * **Front Reset:** Injects the step at the front. The current animation is interrupted, but will restart from its *absolute beginning* later.
* **Step Modifiers (How the step behaves):**
  * **Requeue:** Loops the specific step. Once completed, the hardware pushes this single step back into the queue automatically. ⚠️ **Note:** This is only visually effective when using *relative* color shifts. Requeuing an *absolute* color will just set the light to the exact same color repeatedly.
  * **Direction:** Forces the transition to take the "long way" around the 360-degree color wheel (HSV Hue only).
  * **Name:** Tags the step with a custom string (e.g., `sunrise`) to track hardware events.

---

## 2. Structured Actions (UI & YAML)

These actions use standard structured data. This is the recommended approach when building automations via the Home Assistant UI.

* **`fhem_rgbwwcontroller.animation_hsv`**
* **`fhem_rgbwwcontroller.animation_rgbww`**

### Payload Parameters (`anim_definitions`)
You provide a list of steps. Each step configures the concepts explained above.

| Parameter | Type | Description |
| :--- | :--- | :--- |
| **Color Targets** | Integer | `hue`, `saturation`, `brightness`, `color_temp_kelvin` (or `red`, `green`, etc. for RGBWW). |
| **`transition_mode`** | String | `time` or `speed`. |
| **`transition_value`** | Integer | Duration in **milliseconds** (if mode is `time`), or rate per minute (if mode is `speed`). |
| **`stay`** | Integer | Hold time in **milliseconds**. |
| **`queue_policy`** | String | `single`, `back`, `front`, or `front_reset`. |
| **`requeue`** | Boolean | `true` or `false`. |

### Example (YAML)
*A two-step sequence: Fade to Green over 2 seconds, hold for 5 seconds, then fade to Blue and hold.*
```yaml
action: fhem_rgbwwcontroller.animation_hsv
target:
  entity_id: light.my_led_strip
data:
  anim_definitions:
    # Step 1: Clear the queue and fade to Green
    - hue: 120
      saturation: 100
      brightness: 100
      transition_mode: time
      transition_value: 2000
      stay: 5000
      queue_policy: single
    # Step 2: Append a fade to Blue to the queue
    - hue: 240
      saturation: 100
      brightness: 100
      transition_mode: time
      transition_value: 2000
      stay: 5000
      queue_policy: back
```

---

## 3. CLI String Actions (Compact Syntax)

For advanced users, scripts, or Node-RED, defining long YAML lists can be cumbersome. The CLI actions allow you to compress entire sequences into a single string.

* **`fhem_rgbwwcontroller.animation_cli_hsv`**
* **`fhem_rgbwwcontroller.animation_cli_rgbww`**

### Syntax Rules
`[Color] [Transition] [StayTime] [Flags]; [NextStep]...`
* Steps are separated by semicolons (`;`). Parameters are separated by spaces.
* Color values are comma-separated. Omit a value to keep its current state (e.g., `,,50` changes only brightness). Add `+` or `-` for relative shifts.
* **Transition:** Defined in seconds (e.g., `5`) or speed prefixed with `s` (e.g., `s200`). **Defaults to `0` (instant) if omitted.**
* **Stay Time:** Suffixed with `s` (e.g., `10s`). **Defaults to `0s` if omitted.**

### Mapping Flags to Core Concepts
Instead of dropdowns, the CLI uses letter flags for Queue Policies and Modifiers.

| Flag | Meaning | Type |
| :--- | :--- | :--- |
| *(none)* | Single | Queue Policy (Default) |
| **`q`** | Back | Queue Policy |
| **`f`** | Front | Queue Policy |
| **`e`** | Front Reset | Queue Policy |
| **`r`** | Requeue | Modifier |
| **`d`** | Direction | Modifier |
| **`:name:`**| Name | Modifier |

⚠️ **Important Rule for CLI Sequences:** When chaining multiple steps with `;`, **every step after the first must include a queue policy flag** (usually `q`). If omitted, it defaults to `Single` and instantly clears the queue!

### CLI Examples

**1. Continuous Rainbow (Relative Hue + Requeue)**
Increases Hue by 15 degrees over 1 second, repeatedly forever.
```yaml
action: fhem_rgbwwcontroller.animation_cli_hsv
target:
  entity_id: light.living_room
data:
  # Hue +15 degrees, 1s transition, Requeue modifier (r)
  anim_definition_command: "+15,,, 1 r"
```

**2. Sunrise Sequence (Absolute Colors + Queue Policy)**
Dim red instantly -> fade to orange over 60s -> wait 5s -> fade to bright warm white over 60s.
*(Note how the first step omits the transition time, defaulting to 0).*
```yaml
action: fhem_rgbwwcontroller.animation_cli_hsv
target:
  entity_id: light.bedroom
data:
  anim_definition_command: "0,100,1 :start:; 30,100,50 60 5s q; ,,100,2700 60 q"
```

**3. Immediate "Flash" Override (RGBWW)**
Flash Red immediately, hold 1s, then let the previous animation continue exactly where it paused.
*(Both steps omit the transition time, defaulting to 0. The second step also omits stay time).*
```yaml
action: fhem_rgbwwcontroller.animation_cli_rgbww
target:
  entity_id: light.hallway
data:
  # Step 1: Front Reset (e) sets red, holds 1s
  # Step 2: Front (f) turns off
  anim_definition_command: "1023,0,0,0,0 1s e; 0,0,0,0,0 f"
```

---

## 4. Playback Control (`control_channel`)

The `control_channel` action allows you to intervene in the hardware playback state of specific channels without sending new colors.

* **Action:** `fhem_rgbwwcontroller.control_channel`
* **Commands:** `pause`, `continue`, `stop` (Stops transition and clears queue).
* **Channels:** `hue`, `saturation`, `value`, `color_temp`

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