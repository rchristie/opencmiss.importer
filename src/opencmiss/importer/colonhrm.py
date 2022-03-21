import csv
import os.path

from opencmiss.utils.zinc.field import create_field_finite_element, create_field_coordinates
from opencmiss.zinc.context import Context
from opencmiss.zinc.field import Field
from opencmiss.zinc.status import OK as ZINC_OK

from opencmiss.importer.base import valid
from opencmiss.importer.errors import OpenCMISSImportInvalidInputs, OpenCMISSImportUnknownParameter, OpenCMISSImportColonHRMError


def import_data(inputs, output_directory):
    if type(inputs) == list and len(inputs):
        inputs = inputs[0]

    if not valid(inputs, parameters("input")):
        raise OpenCMISSImportInvalidInputs(f"Invalid input given to importer: {identifier()}")

    manometry_data = inputs
    output = None

    context = Context("HRM")
    region = context.getDefaultRegion()
    field_module = region.getFieldmodule()

    # Determine times for time keeper.
    with open(manometry_data) as f:
        csv_reader = csv.reader(f, delimiter='\t')

        times = []
        try:
            for row in csv_reader:
                times.append(float(row[0]))
        except UnicodeDecodeError:
            raise OpenCMISSImportColonHRMError("Colon HRM file is not valid.")

    with open(manometry_data) as f:
        csv_reader = csv.reader(f, delimiter='\t')
        first_row = True
        for row in csv_reader:
            time = float(row.pop(0))
            stimulation = float(row.pop(0))
            values = row[:]
            if first_row:
                _setup_nodes(field_module, times, values)
                first_row = False

            pressure_field = field_module.findFieldByName("pressure")
            stimulation_field = field_module.findFieldByName("stimulation")

            data_points = field_module.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_DATAPOINTS)
            for index, value in enumerate(values):
                data_point = data_points.findNodeByIdentifier(index + 1)
                field_cache = field_module.createFieldcache()
                field_cache.setNode(data_point)
                field_cache.setTime(time)
                pressure_field.assignReal(field_cache, float(value))
                stimulation_field.assignReal(field_cache, stimulation)

    filename_parts = os.path.splitext(os.path.basename(manometry_data))
    output_exf = os.path.join(output_directory, filename_parts[0] + ".exf")
    result = region.writeFile(output_exf)
    if result == ZINC_OK:
        output = output_exf

    return output


def _setup_nodes(field_module, times, values):
    num_sensors = len(values)
    coordinate_field = create_field_coordinates(field_module)
    pressure_field = create_field_finite_element(field_module, "pressure", 1, type_coordinate=False)
    stimulation_field = create_field_finite_element(field_module, "stimulation", 1, type_coordinate=False)
    data_points = field_module.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_DATAPOINTS)

    data_template = data_points.createNodetemplate()
    data_template.defineField(coordinate_field)
    data_template.defineField(pressure_field)
    data_template.defineField(stimulation_field)

    time_sequence = field_module.getMatchingTimesequence(times)

    data_template.setTimesequence(pressure_field, time_sequence)
    data_template.setTimesequence(stimulation_field, time_sequence)

    field_cache = field_module.createFieldcache()
    for index, value in enumerate(values):
        pos = [index / (num_sensors - 1), 0.0, 0.0]
        node = data_points.createNode(-1, data_template)
        field_cache.setNode(node)
        coordinate_field.assignReal(field_cache, pos)


def identifier():
    return "colonhrm"


def parameters(parameter_name=None):
    importer_parameters = {
        "version": "0.1.0",
        "id": identifier(),
        "input": {
            "mimetype": "text/tab-separated-values",
        },
        "output": {
            "mimetype": "text/x.vnd.abi.exf+plain",
        }
    }

    if parameter_name is not None:
        if parameter_name in importer_parameters:
            return importer_parameters[parameter_name]
        else:
            raise OpenCMISSImportUnknownParameter(f"Importer '{identifier()}' does not have parameter: {parameter_name}")

    return importer_parameters