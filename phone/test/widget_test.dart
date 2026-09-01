import 'package:flutter_test/flutter_test.dart';
import 'package:aether_phone/main.dart';

void main() {
  testWidgets('app title', (tester) async {
    await tester.pumpWidget(const DeskPhoneApp());
    expect(find.textContaining('Aether'), findsWidgets);
  });
}
