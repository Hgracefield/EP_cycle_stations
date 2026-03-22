// ===============================================
// File: Dashboard.dart
// Purpose: 관리자 입장에서 정보를 쉽게 알아볼 수 있는 대시보드 페이지
//
// Change Log
// - 22-Mar-2026, Chansol Park
//   - Initial creation using Codex
// ===============================================
import 'package:flutter/material.dart';

// This widget is the main reusable spreadsheet subpage.
// It is designed to be placed inside an existing Flutter app screen flow,
// which is why the file does not contain a separate app entry point.
class StationExcelPage extends StatefulWidget {
  const StationExcelPage({super.key});

  @override
  State<StationExcelPage> createState() => _StationExcelPageState();
}

// This widget keeps the older page name available for compatibility.
// If another part of the project still refers to "Dashboard", it can continue
// to work without changing routing or imports.
class Dashboard extends StatefulWidget {
  const Dashboard({super.key});

  @override
  State<Dashboard> createState() => _DashboardState();
}

// This abstract base state holds the spreadsheet logic shared by both
// StationExcelPage and Dashboard.
// Using one shared state implementation avoids duplicating the same table
// behavior in two separate classes.
abstract class _StationExcelPageBaseState<T extends StatefulWidget>
    extends State<T> {
  // These are the fixed station IDs that define the spreadsheet rows.
  // They are constant because the current design treats rows as predefined,
  // while columns can grow dynamically over time.
  static const List<String> _stationIds = <String>[
    'ST-481',
    'ST-2425',
    'ST-1331',
    'ST-454',
    'ST-453',
    'ST-1482',
  ];

  // The first column contains station IDs, so it uses its own fixed width.
  // Keeping a stable width helps the layout feel consistent and spreadsheet-like.
  static const double _stationColumnWidth = 140;

  // Every data column uses the same width so the grid stays visually uniform.
  // This makes horizontal scrolling more predictable when many columns are added.
  static const double _dataColumnWidth = 170;

  // This controller is still needed because the "New column" input remains
  // editable even though the spreadsheet itself is read-only.
  // We read its current value when the user submits or presses the add button.
  final TextEditingController _newColumnController = TextEditingController();

  // This controller manages vertical scrolling for the spreadsheet area.
  // It also allows the vertical Scrollbar widget to stay synchronized with the
  // actual scroll position.
  final ScrollController _verticalScrollController = ScrollController();

  // This controller manages horizontal scrolling for the table width.
  // It is especially useful when the number of columns becomes wider than the
  // available screen space.
  final ScrollController _horizontalScrollController = ScrollController();

  // This list stores the column names currently visible in the spreadsheet.
  // It starts with the predefined initial columns and grows when the user adds
  // new ones through the input field.
  final List<String> _columns = <String>['cluster', 'weight', 'note'];

  // This is the main table data structure used by the page.
  // Structure:
  //   stationId -> columnName -> cellValue
  //
  // Example:
  //   {
  //     'ST-481': {
  //       'cluster': 'A',
  //       'weight': '0.82',
  //       'note': 'checked'
  //     }
  //   }
  //
  // A nested map is a good fit here because:
  // 1. The outer key identifies the row
  // 2. The inner key identifies the column
  // 3. The final value is the displayed cell content
  //
  // This keeps the data model simple and easy to access from the UI.
  final Map<String, Map<String, String>> _tableData =
      <String, Map<String, String>>{};

  @override
  void initState() {
    // Always call super.initState() first so Flutter can complete its own
    // initialization before this widget sets up custom state.
    super.initState();

    // Build the initial spreadsheet data row by row.
    // Every station gets its own inner map so the table starts as a complete
    // rectangle with values for every predefined row and column.
    for (final stationId in _stationIds) {
      // This map will hold all cell values for one specific station row.
      final Map<String, String> rowData = <String, String>{};

      // Fill every starting column with an empty string.
      // Empty strings are used instead of null to make display logic simpler:
      // the table can always render a string value for each cell.
      for (final column in _columns) {
        //  ******** Here, you can show up chosen colum's data initial value
        // if (column == 'cluster') {
        //   rowData[column] = 'A'; // Value always will be A as String
        // }
        rowData[column] = '';
      }

      // Store the fully initialized row into the main data map.
      _tableData[stationId] = rowData;
    }
  }

  @override
  void dispose() {
    // Dispose controllers that are still actively used by the page.
    // This is important because controllers hold resources and listeners;
    // disposing them prevents memory leaks when the page is removed.
    _newColumnController.dispose();
    _verticalScrollController.dispose();
    _horizontalScrollController.dispose();

    // Call the parent cleanup last so all page-specific resources are released
    // before Flutter finalizes the state object.
    super.dispose();
  }

  void _addColumn() {
    // Read the text from the input field and trim spaces from both ends.
    // Trimming helps avoid accidental column names such as " note " that look
    // similar but are technically different keys.
    final String columnName = _newColumnController.text.trim();

    // Stop early if the user did not type anything meaningful.
    // A blank column name would not be useful in the UI or the data model.
    if (columnName.isEmpty) {
      _showMessage('Enter a column name first.');
      return;
    }

    // Prevent duplicate column names.
    // Since column names are used as keys in the nested row maps, duplicates
    // would make the table structure ambiguous and error-prone.
    if (_columns.contains(columnName)) {
      _showMessage('Column "$columnName" already exists.');
      return;
    }

    // setState tells Flutter that the widget's visible data is changing and
    // the UI should be rebuilt afterward.
    setState(() {
      // Add the new column name so the header row and each data row will render
      // an extra cell in the table.
      _columns.add(columnName);

      // Initialize the new column for every existing row.
      // This keeps the table rectangular so every row always has the same set
      // of columns.
      for (final stationId in _stationIds) {
        _tableData[stationId]![columnName] = '';
      }
    });

    // Clear the input so the field is ready for the next column name.
    _newColumnController.clear();

    // Remove focus from the input to give better UX, especially on mobile
    // where this may also dismiss the on-screen keyboard.
    FocusScope.of(context).unfocus();
  }

  void _printTableData() {
    // This helper prints the current spreadsheet contents to the debug console.
    // It is useful for development because it lets you verify that the UI is
    // backed by the expected in-memory data structure.
    debugPrint('Station table data:');

    // Print row data in the same column order used by the table UI so the
    // console output is easier to compare with what the user sees on screen.
    for (final stationId in _stationIds) {
      final Map<String, String> rowSnapshot = <String, String>{};
      for (final column in _columns) {
        rowSnapshot[column] = _tableData[stationId]![column] ?? '';
      }

      // Example output:
      // ST-481 -> {cluster: , weight: , note: }
      debugPrint('$stationId -> $rowSnapshot');
    }

    // Show a visual confirmation after printing so the user knows the button
    // action completed successfully even if the console is not visible.
    _showMessage('Current table data printed to the console.');
  }

  void _showMessage(String message) {
    // SnackBar is used for lightweight feedback messages such as validation
    // errors or success notifications.
    // The current snackbar is hidden first so repeated actions do not stack
    // multiple messages on top of each other.
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Table _buildSpreadsheetTable() {
    // The Table widget allows us to create a spreadsheet-like grid with
    // explicit column widths and visible borders.
    // Here we define the width for each column index.
    final Map<int, TableColumnWidth> columnWidths = <int, TableColumnWidth>{
      // Column 0 is the fixed station ID label column.
      0: const FixedColumnWidth(_stationColumnWidth),
    };

    // Add one fixed width entry for every data column.
    // Using consistent widths keeps the grid visually neat and predictable.
    for (int index = 0; index < _columns.length; index++) {
      columnWidths[index + 1] = const FixedColumnWidth(_dataColumnWidth);
    }

    // Build the spreadsheet using:
    // 1. One header row
    // 2. One data row per station
    //
    // TableBorder.all is what creates the Excel-like grid lines.
    return Table(
      border: TableBorder.all(color: const Color(0xFFBDC7D3), width: 1),
      defaultVerticalAlignment: TableCellVerticalAlignment.middle,
      columnWidths: columnWidths,
      children: <TableRow>[
        // The first row is the table header:
        // - first cell = static "Station ID"
        // - remaining cells = the current column names
        TableRow(
          children: <Widget>[
            _buildStaticHeaderCell('Station ID'),
            ..._columns.map(_buildEditableHeaderCell),
          ],
        ),
        // Create one table row for every station ID.
        // Each generated row begins with the station label, followed by the
        // read-only text cells for every column currently in _columns.
        ..._stationIds.map((stationId) {
          return TableRow(
            children: <Widget>[
              _buildStationIdCell(stationId),
              ..._columns.map((column) {
                return _buildEditableDataCell(
                  stationId: stationId,
                  column: column,
                );
              }),
            ],
          );
        }),
      ],
    );
  }

  Widget _buildStaticHeaderCell(String label) {
    // This builds the top-left header cell.
    // It is separate from the other header cells because it labels the row ID
    // column rather than representing a dynamic spreadsheet field.
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      alignment: Alignment.centerLeft,
      color: const Color(0xFFE6EBF1),
      child: Text(
        label,
        style: const TextStyle(
          fontWeight: FontWeight.w700,
          color: Color(0xFF1F2937),
        ),
      ),
    );
  }

  Widget _buildEditableHeaderCell(String column) {
    // Despite the method name, the current header is read-only.
    // The method name is preserved to avoid unnecessary refactoring outside the
    // requested scope.
    //
    // Each dynamic column name is displayed inside a styled container so the
    // header row visually matches the rest of the spreadsheet grid.
    return Container(
      height: 56,
      color: const Color(0xFFF3F6F9),
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Text(
        column,
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontWeight: FontWeight.w600,
          color: Color(0xFF111827),
        ),
      ),
    );
  }

  Widget _buildStationIdCell(String stationId) {
    // This renders the left-side row label cell for one station.
    // It uses a slightly different background color to distinguish row headers
    // from regular data cells, similar to spreadsheet applications.
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      alignment: Alignment.centerLeft,
      color: const Color(0xFFF8FAFC),
      child: Text(
        stationId,
        style: const TextStyle(
          fontWeight: FontWeight.w600,
          color: Color(0xFF111827),
        ),
      ),
    );
  }

  Widget _buildEditableDataCell({
    required String stationId,
    required String column,
  }) {
    // This builds one read-only data cell.
    // The value is looked up directly from the nested _tableData structure
    // using both the row key (stationId) and the column key (column).
    //
    // The `?? ''` fallback guarantees that the UI always receives a string to
    // display, even if a value is missing unexpectedly.
    return Container(
      height: 52,
      color: Colors.white,
      alignment: Alignment.center,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Text(
        _tableData[stationId]![column] ?? '',
        textAlign: TextAlign.center,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Access the current text theme from the surrounding app theme.
    // This helps the page blend in visually with the rest of the app.
    final TextTheme textTheme = Theme.of(context).textTheme;

    // Scaffold provides the standard page structure:
    // - AppBar at the top
    // - Page body below it
    return Scaffold(
      appBar: AppBar(title: const Text('Station Excel Page')),
      body: SafeArea(
        // SafeArea prevents content from being hidden behind system UI areas
        // such as the status bar, notch, or gesture areas.
        child: Padding(
          padding: const EdgeInsets.all(16),
          // The page is built vertically from top to bottom:
          // 1. Title
          // 2. Description
          // 3. Controls for adding columns / printing data
          // 4. Column summary
          // 5. Expandable spreadsheet region
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Main page title.
              Text(
                'Station spreadsheet',
                style: textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              // Supporting explanation so users understand the current behavior:
              // the table is read-only, but columns can still be added.
              Text(
                'Headers and cells are read-only. You can still add more columns.',
                style: textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF5F6B7A),
                ),
              ),
              const SizedBox(height: 16),
              // Wrap is used instead of Row so the controls can move onto
              // multiple lines on smaller screens rather than overflowing.
              Wrap(
                spacing: 12,
                runSpacing: 12,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: <Widget>[
                  // This input is still editable because users can add new
                  // column names even though the spreadsheet cells themselves
                  // are read-only.
                  SizedBox(
                    width: 240,
                    child: TextField(
                      controller: _newColumnController,
                      textInputAction: TextInputAction.done,
                      decoration: InputDecoration(
                        labelText: 'New column',
                        hintText: 'Example: status',
                        filled: true,
                        fillColor: Colors.white,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      // Allow the user to submit directly from the keyboard.
                      onSubmitted: (_) => _addColumn(),
                    ),
                  ),
                  // Adds the typed column name to the spreadsheet.
                  FilledButton(
                    onPressed: _addColumn,
                    child: const Text('Add Column'),
                  ),
                  // Prints the current in-memory table data for debugging.
                  OutlinedButton(
                    onPressed: _printTableData,
                    child: const Text('Print Data'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // This summary box displays the current active column list.
              // It gives the user quick feedback after new columns are added.
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border.all(color: const Color(0xFFD6DEE8)),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  'Columns (${_columns.length}): ${_columns.join(', ')}',
                  style: textTheme.bodyMedium,
                ),
              ),
              const SizedBox(height: 16),
              // Expanded makes the spreadsheet area take up all remaining
              // vertical space below the controls and summary.
              Expanded(
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    border: Border.all(color: const Color(0xFFD6DEE8)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    // Outer scrollbar + outer scroll view handle vertical
                    // movement for the spreadsheet container.
                    child: Scrollbar(
                      controller: _verticalScrollController,
                      thumbVisibility: true,
                      child: SingleChildScrollView(
                        controller: _verticalScrollController,
                        padding: const EdgeInsets.all(12),
                        // Inner scrollbar + inner scroll view handle horizontal
                        // movement for wide tables.
                        //
                        // This nested scroll setup is important because a
                        // spreadsheet often needs to scroll in two directions:
                        // down for more rows and sideways for more columns.
                        child: Scrollbar(
                          controller: _horizontalScrollController,
                          thumbVisibility: true,
                          child: SingleChildScrollView(
                            controller: _horizontalScrollController,
                            scrollDirection: Axis.horizontal,
                            // The full bordered table is generated by the
                            // helper method above so the build method stays
                            // easier to read.
                            child: _buildSpreadsheetTable(),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Concrete state class for StationExcelPage.
// It inherits all spreadsheet behavior from the shared base state.
class _StationExcelPageState
    extends _StationExcelPageBaseState<StationExcelPage> {}

// Concrete state class for the compatibility Dashboard widget.
// It reuses the exact same shared spreadsheet implementation.
class _DashboardState extends _StationExcelPageBaseState<Dashboard> {}
