"""Press the buttons drawn inside a building's scene, as street.js does when one is clicked or its key pressed.

AppTest does not run JavaScript, so these send the same map event the scene sends: {"action": "building",
"key": ...} (or "leave" for Esc) through the street_map component.
"""
import json
from itertools import count

from streamlit.proto.WidgetStates_pb2 import WidgetState

_ids = count(1000)


def scene(app):
    """The interior data the app sends to the game view."""
    component = next(iter(app.get("component_instance")))
    return json.loads(component.proto.json_args).get("interior") or {}


def scene_labels(app):
    """Label -> key of every button drawn in the scene."""
    return {label: key for key, label in scene(app).get("keys", [])}


def press(app, key):
    component = next(iter(app.get("component_instance")))
    event = {"segments": [{"dx": 0, "dy": 0, "seconds": 0}], "action": "leave" if key == "escape" else "building",
             "key": key, "id": next(_ids)}
    states = app._tree.get_widget_states()
    state = WidgetState(id=component.proto.id)
    state.json_value = json.dumps(event)
    states.widgets.append(state)
    app._run(states)
    assert not app.exception
    return app


def click_scene(app, label):
    """Click the scene button with this label."""
    return press(app, scene_labels(app)[label])
