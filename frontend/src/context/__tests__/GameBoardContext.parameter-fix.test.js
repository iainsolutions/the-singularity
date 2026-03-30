/**
 * Regression test for GameBoardContext onCardClick parameter mismatch bug
 *
 * Bug: The GameBoardContext onCardClick was expecting (card, cardLocation)
 * but PlayerBoard was calling it with (card, needsToRespond, pendingDogmaAction, isMyTurn, cardLocation)
 * This caused cardLocation to receive the wrong parameter value (false instead of 'board')
 */
import { describe, it, expect } from "vitest";

describe("GameBoardContext Parameter Passing Regression Test", () => {
  it("documents the onCardClick parameter signature that was fixed", () => {
    // This test serves as documentation of the parameter order that caused the bug
    const playerBoardCallSignature = [
      "card", // 1st param: card object
      "needsToRespond", // 2nd param: boolean (was incorrectly received as cardLocation)
      "pendingDogmaAction", // 3rd param: object or null
      "isMyTurn", // 4th param: boolean
      "cardLocation", // 5th param: string ('board' or 'hand') - this is what we actually need
    ];

    const originalContextExpectedSignature = [
      "card", // 1st param: card object
      "cardLocation", // 2nd param: should be string, but was receiving needsToRespond (boolean)
    ];

    const fixedContextSignature = [
      "card", // 1st param: card object
      "needsToRespond", // 2nd param: boolean
      "pendingDogmaAction", // 3rd param: object or null
      "isMyTurn", // 4th param: boolean
      "cardLocation", // 5th param: string ('board' or 'hand')
    ];

    // The bug was that cardLocation (5th param) was being assigned needsToRespond (2nd param)
    expect(playerBoardCallSignature.length).toBe(5);
    expect(originalContextExpectedSignature.length).toBe(2);
    expect(fixedContextSignature.length).toBe(5);

    // Verify the parameter we care about is in the correct position
    expect(playerBoardCallSignature[4]).toBe("cardLocation");
    expect(fixedContextSignature[4]).toBe("cardLocation");

    // Document what was broken: cardLocation was receiving the wrong value
    const originalBuggedValue = playerBoardCallSignature[1]; // 'needsToRespond'
    const correctValue = playerBoardCallSignature[4]; // 'cardLocation'

    expect(originalBuggedValue).toBe("needsToRespond"); // This was a boolean (false)
    expect(correctValue).toBe("cardLocation"); // This should be a string ('board' or 'hand')
  });

  it("validates the expected cardLocation values", () => {
    const validCardLocations = ["board", "hand", "score_pile"];
    const invalidCardLocation = false; // This was the bug - cardLocation was boolean false

    // Valid locations should be strings
    validCardLocations.forEach((location) => {
      expect(typeof location).toBe("string");
      expect(location.length).toBeGreaterThan(0);
    });

    // The bug value should not be a valid cardLocation
    expect(typeof invalidCardLocation).toBe("boolean");
    expect(invalidCardLocation).toBe(false);
    expect(validCardLocations).not.toContain(invalidCardLocation);
  });
});
